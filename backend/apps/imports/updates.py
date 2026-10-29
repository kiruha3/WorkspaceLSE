"""Explicit corrections of nonoperational source history; never native events."""
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction,IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.services import audit,check_version
from apps.expertises.history import FIELDS
from apps.expertises.models import Expertise,HistoricalWork,HistoricalParticipant
from apps.intake.models import Material,Receipt
from apps.issuance.models import IssuePackage
from apps.references.models import Department,Specialty
from apps.personnel.models import Employee
from .models import ImportBatch,ImportRow,ImportSelection,ImportApplication,ImportApplicationItem
from .application import require_apply,lock_numbers,source_facts
from .reconciliation import identity_blockers,selection_data,validate_mapping


def plain(value):
    return json.loads(json.dumps(value,cls=DjangoJSONEncoder))


def current_values(work):
    history=work.historical
    return plain({**{field:getattr(history,field) for field in FIELDS},
        'registration_number':work.registration_number,'historical_number':work.historical_number,
        'sequence':work.sequence,'year':work.year,'category_code':work.category_code,'department_id':str(work.department_id),
        'specialty_id':str(work.specialty_id) if work.specialty_id else None,
        'received_on':work.receipt.received_at,'sender_name':work.receipt.sender_name,'state':work.state,
        'appointment_nature':work.appointment_nature,'is_commission':work.is_commission,
        'complex_known':history.complex_known,'complex_group_key':work.complex_group.title if work.complex_group_id else None,
        'statistics_confirmed':history.statistics_confirmed,
        'employee_ids':sorted(str(p.employee_id) for p in history.participants.all())})


def source_values(row,selection,*,as_of=None):
    facts=row.facts
    return plain({**source_facts(row,as_of=as_of),
        'registration_number':facts['registration_number'],'historical_number':facts.get('historical_number') or '',
        'sequence':facts['sequence'],'year':facts['year'],'category_code':facts['category_code'],
        'department_id':selection['department_id'],'specialty_id':selection['specialty_id'],
        'received_on':facts['received_on'],'sender_name':facts.get('authority_name','')[:500],'state':facts['state'],
        **{key:selection[key] for key in ('appointment_nature','is_commission','complex_known','complex_group_key','statistics_confirmed')},
        'employee_ids':sorted(selection['employee_ids'])})


SOURCE_UPDATE_FIELDS=set(FIELDS)|{'specialty_id','employee_ids','state','received_on','sender_name','historical_number','statistics_confirmed'}


def accepted_source_baseline(work):
    """Audit after-snapshots are not acceptance of their unselected fields."""
    history=work.historical
    original=ImportApplicationItem.objects.filter(work=work,action='created').select_related('row__selection').order_by('application__created_at','pk').first()
    source=original.row if original else history.source_row
    choice=selection_data(getattr(source,'selection',None))
    if choice is None:return None
    baseline=source_values(source,choice,as_of=timezone.localtime(history.created_at).date())
    applications=ImportApplication.objects.filter(links__contains=[{'expertise_id':str(work.pk),'action':'updated'}]).order_by('created_at','pk')
    for application in applications:
        for link in application.links:
            if link.get('expertise_id')!=str(work.pk) or link.get('action')!='updated' or 'after' not in link:continue
            accepted=link.get('accepted_fields')
            if accepted is None:baseline=link['after'].copy()
            else:
                for field in accepted:baseline[field]=link['after'][field]
    return baseline


def validate_selected_values(work,before,target,accepted):
    """Check the actual merged record without requiring missing archival data."""
    values={**before,**{field:target[field] for field in accepted}}
    date_fields={'received_on','completed_on','return_decided_on','issued_on','state'}
    if accepted & date_fields:
        for field in ('completed_on','return_decided_on','issued_on'):
            value=values[field]
            if value and value<values['received_on']:
                raise ValidationError({field:'После выбранных изменений дата окажется раньше поступления. Выберите связанные даты вместе.'})
            if value and value>timezone.localdate().isoformat():
                raise ValidationError({field:'Фактическая дата не может быть будущей. Проверьте связанные даты.'})
        if values['state']!='completed' and values['completed_on']:
            raise ValidationError({'state':'Вместе с этим состоянием примите очистку даты окончания; она не может оставаться у незавершённой работы.'})
        if values['state']!='without_execution' and values['return_decided_on']:
            raise ValidationError({'state':'С состоянием несовместима сохранённая дата решения без исполнения. Уточните её в карточке.'})
    if 'result_kind' in accepted:
        kind=values['result_kind']
        if kind and ((work.category_code=='6')!=(kind=='research_act')):
            raise ValidationError({'result_kind':'Вид результата не соответствует категории номера.'})
        if work.historical.sndz_reason_id and kind!='sndz':
            raise ValidationError({'result_kind':'Сохранена причина полного СНДЗ. Сначала согласованно уточните результат и причину в карточке.'})
    if 'state' in accepted and work.historical.return_reason_id and values['state']!='without_execution':
        raise ValidationError({'state':'Сохранена причина возврата. Уточните её вместе с состоянием в карточке.'})
    counts={'questions','categorical','probable','unresolved','statistics_confirmed'}
    if accepted & counts and values['statistics_confirmed']:
        numbers=[values[field] for field in ('questions','categorical','probable','unresolved')]
        if any(value is None for value in numbers) or numbers[0]!=sum(numbers[1:]):
            raise ValidationError({'questions':'Выбранные поля нарушат подтверждённую статистику Q/R/S/T. Примите согласованные количества вместе.'})
    if accepted & counts and work.historical.allocations_complete:
        total=sum(work.historical.unresolved_allocations.values_list('count',flat=True))
        if values['unresolved'] is None or total!=values['unresolved']:
            raise ValidationError({'unresolved':'Количество не совпадёт с подтверждёнными причинами нерешённых вопросов. Сначала уточните распределение в карточке.'})


def update_preview(row,work,*,selective=False,proposed_selection=None):
    blockers=[]
    result={'eligible':False,'blockers':blockers,'changes':[],
        'expected_work_version':work.version,'expected_source_row_id':None,'previous_selection':None}
    history=getattr(work,'historical',None)
    if work.origin_kind!='historical' or history is None:
        blockers.append('Это не перенесённая историческая работа.');return result
    if work.reopenings.exists():
        blockers.append('Есть локальный возврат в работу. Источник его не перезаписывает.');return result
    if not selective and history.corrections.exists():blockers.append('Есть ручное уточнение исторических сведений. Источник его не перезаписывает.')
    if getattr(work,'case_details',None) is not None:blockers.append('Есть ручные сведения дела в рабочей карточке. Источник их не перезаписывает.')
    if getattr(work,'classification',None) is not None:blockers.append('Есть ручная классификация работы. Источник её не перезаписывает.')
    if getattr(work,'timing',None) is not None:blockers.append('Есть ручные сведения о сроках. Источник их не перезаписывает.')
    previous=history.source_row;result['expected_source_row_id']=str(previous.pk)
    previous_choice=getattr(previous,'selection',None)
    item=getattr(previous,'application_item',None)
    if previous_choice is None or item is None:
        blockers.append('Нет подтверждённой базы прежнего переноса.');return result
    choice=selection_data(previous_choice);result['previous_selection']=choice
    if history.operational or work.receipt.status!='historical' or work.receipt.basis_document_id:
        blockers.append('Работа уже продолжена в новом учёте. Источник её не перезаписывает.')
    if any(manager.exists() for manager in (work.assignments,work.suspensions,work.deadline_events,work.result_revisions,work.closures)) or IssuePackage.objects.filter(material_id=work.material_id).exists():
        blockers.append('Есть события или комплект нового учёта. Нужна отдельная корректировка.')
    if work.receipt.expertises.exclude(pk=work.pk).exists():blockers.append('Поступление связано с несколькими работами; требуется совместная корректировка.')
    if (row.batch.created_at<=previous.batch.created_at and not (selective and row.pk==previous.pk)) or (row.batch.source_observed_at and previous.batch.source_observed_at and row.batch.source_observed_at<previous.batch.source_observed_at):
        blockers.append('Снимок не новее применённого источника.')
    if identity_blockers(row):blockers.append('Уточните номер, поступление или состояние в новом источнике.')
    if not selective and row.facts==previous.facts:blockers.append('Сведения источника не изменились.')
    baseline=accepted_source_baseline(work)
    if baseline is None:blockers.append('Нет подтверждённой базы прежнего переноса.');return result
    current=current_values(work)
    if not selective and current!=baseline:blockers.append('Есть ручная правка относительно прежнего переноса. Автоматическое слияние не выполняется.')
    for field in ('registration_number','sequence','year','category_code','department_code'):
        if row.facts.get(field)!=previous.facts.get(field):blockers.append('Номер, категория и фактический отдел этим действием не меняются.');break
    if identity_blockers(row):return result
    selected=getattr(row,'selection',None)
    target_choice=proposed_selection if proposed_selection is not None else selection_data(selected) if selected else {**choice,
        'specialty_id':str(ref.pk) if (ref:=Specialty.objects.filter(code=row.facts.get('specialty_code')).first()) else None,
        'employee_ids':[] if row.facts.get('executor_raw')!=previous.facts.get('executor_raw') else choice['employee_ids']}
    for field in ('appointment_nature','is_commission','complex_known','complex_group_key'):
        if target_choice[field]!=choice[field]:blockers.append('Состав и комплексность обновлением источника не меняются.');break
    target=source_values(row,target_choice)
    result['changes']=[{'field':key,'before':current[key],'after':value} for key,value in target.items() if current[key]!=value]
    if selective:
        result['changes']=[{**change,'conflict':current[change['field']]!=baseline[change['field']]}
            for change in result['changes'] if change['field'] in SOURCE_UPDATE_FIELDS and target[change['field']]!=baseline[change['field']]]
    # Source/apply readers need the meaning of selected references, not the
    # entire personnel editing catalogue. Expose only names used by this diff.
    reference_changes={c['field']:c for c in result['changes'] if c['field'] in ('specialty_id','employee_ids')}
    if change:=reference_changes.get('specialty_id'):
        refs={str(ref.pk):f'{ref.code} · {ref.name}' for ref in Specialty.objects.filter(pk__in=[value for value in (change['before'],change['after']) if value])}
        for side in ('before','after'):change[side+'_label']=refs.get(change[side],'Неизвестно / не заполнено')
    if change:=reference_changes.get('employee_ids'):
        refs={str(person.pk):person.full_name for person in Employee.objects.filter(pk__in=set(change['before']+change['after']))}
        for side in ('before','after'):change[side+'_label']=', '.join(refs[pk] for pk in change[side]) or 'Участники не подтверждены'
    result['eligible']=not blockers
    return result


def _apply_updates(*,actor,batch_id,updates,reason,key,payload):
    with transaction.atomic():
        require_apply(actor)
        batch=get_object_or_404(ImportBatch,pk=batch_id)
        ids=[entry['row_id'] for entry in updates]
        sources=list(batch.rows.filter(pk__in=ids))
        if len(sources)!=len(ids):raise ValidationError({'updates':'Все строки должны принадлежать выбранному снимку.'})
        lock_numbers([source.facts.get('registration_number') or '' for source in sources])
        anchors=list(Expertise.objects.filter(registration_number__in=[r.facts.get('registration_number') for r in sources]).values('pk','material_id','receipt_id'))
        # Same global lock order as activation/production/issuance. No batch lock:
        # creation locks batch before material; acquiring it here would invert that order.
        list(Material.objects.select_for_update().filter(pk__in={a['material_id'] for a in anchors}).order_by('pk'))
        list(Receipt.objects.select_for_update().filter(pk__in={a['receipt_id'] for a in anchors}).order_by('pk'))
        works={w.registration_number:w for w in Expertise.objects.select_for_update().filter(pk__in=[a['pk'] for a in anchors]).order_by('pk')}
        rows=list(ImportRow.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        choices={c.row_id:c for c in ImportSelection.objects.select_for_update().filter(row_id__in=ids).order_by('pk')}
        expected={entry['row_id']:entry for entry in updates}
        def operation():
            require_apply(actor);plans=[]
            # Lock the whole reference set once in a global order, not per row:
            # disjoint work packets can otherwise acquire departments in reverse.
            departments={r.pk:r for r in Department.objects.select_for_update().filter(pk__in={c.department_id for c in choices.values()}).order_by('pk')}
            specialties={r.pk:r for r in Specialty.objects.select_for_update().filter(pk__in={c.specialty_id for c in choices.values() if c.specialty_id}).order_by('pk')}
            people_ids=set().union(*(set(c.employees.values_list('pk',flat=True)) for c in choices.values()))
            locked_people={p.pk:p for p in Employee.objects.select_for_update().filter(pk__in=people_ids).order_by('pk')}
            for source in rows:
                work=works.get(source.facts.get('registration_number'));choice=choices.get(source.pk);entry=expected[source.pk]
                if work is None or choice is None:raise CommandConflict('Нужны существующая работа и новое сохранённое сопоставление.')
                check_version(work,entry['expected_work_version']);check_version(choice,entry['expected_selection_version'])
                accepted=entry.get('accepted_fields')
                info=update_preview(source,work,selective=accepted is not None,proposed_selection=selection_data(choice))
                if info['expected_source_row_id']!=str(entry['expected_source_row_id']):raise CommandConflict('Применённый источник уже изменился. Обновите сверку.')
                if not info['eligible']:raise CommandConflict(' '.join(info['blockers']))
                if accepted is not None and (not accepted or len(set(accepted))!=len(accepted) or not set(accepted)<={c['field'] for c in info['changes']}):
                    raise CommandConflict('Выберите только показанные изменённые поля; обновите перечень.')
                department=departments[choice.department_id]
                specialty=specialties.get(choice.specialty_id)
                validate_mapping(source,department,specialty,choice.statistics_confirmed)
                people=[locked_people[pk] for pk in choice.employees.values_list('pk',flat=True)]
                target=source_values(source,selection_data(choice))
                before=current_values(work)
                if accepted is not None:validate_selected_values(work,before,target,set(accepted))
                plans.append((source,work,choice,target,people,before,set(accepted) if accepted is not None else None))
            application=ImportApplication.objects.create(batch=batch,actor=actor,reason=reason);links=[]
            for source,work,choice,target,people,before,accepted in plans:
                previous_id=work.historical.source_row_id
                history=work.historical
                for field,value in source_facts(source).items():
                    if accepted is None or field in accepted:setattr(history,field,value)
                if accepted is None or 'statistics_confirmed' in accepted:history.statistics_confirmed=choice.statistics_confirmed
                history.source_row=source;history.save()
                wanted={p.pk for p in people};present={p.employee_id for p in history.participants.all()}
                if accepted is None or 'employee_ids' in accepted:
                    history.participants.filter(employee_id__in=present-wanted).delete()
                    HistoricalParticipant.objects.bulk_create([HistoricalParticipant(history=history,employee=p) for p in people if p.pk not in present])
                if accepted is None or 'state' in accepted:work.state=target['state']
                if accepted is None or 'specialty_id' in accepted:work.specialty_id=choice.specialty_id
                if accepted is None or 'historical_number' in accepted:work.historical_number=target['historical_number']
                work.version+=1
                work.save(update_fields=['state','specialty','historical_number','version'])
                receipt=work.receipt
                if accepted is None or accepted & {'received_on','sender_name'}:
                    if accepted is None or 'received_on' in accepted:receipt.received_at=source.facts['received_on']
                    if accepted is None or 'sender_name' in accepted:receipt.sender_name=target['sender_name']
                    receipt.version+=1;receipt.save(update_fields=['received_at','sender_name','version'])
                # Read-back serializer supplies JSON dates/decimals consistently.
                receipt.refresh_from_db();after=current_values(work)
                links.append({'row_id':str(source.pk),'expertise_id':str(work.pk),'action':'updated',
                    'previous_source_row_id':str(previous_id),'before':before,'after':after,'version':work.version,
                    **({'accepted_fields':sorted(accepted)} if accepted is not None else {})})
                previous_item=ImportApplicationItem.objects.filter(row=source).first()
                if previous_item is None:ImportApplicationItem.objects.create(application=application,row=source,work=work,action='updated')
                elif accepted is None or previous_item.work_id!=work.pk:raise CommandConflict('Строка уже применена другой командой. Обновите сверку.')
            application.links=links;application.save(update_fields=['links'])
            event=audit(actor,'imports.update',application,{'batch_id':str(batch.pk),'items':links},reason)
            return {'id':str(event.pk),'application_id':str(application.pk)}
        return execute_once(actor=actor,action='imports.update',key=key,payload={'batch_id':str(batch.pk),'data':payload},operation=operation)


def apply_updates(**kwargs):
    try:return _apply_updates(**kwargs)
    except IntegrityError as error:
        if getattr(error.__cause__,'sqlstate',None)=='23505':raise CommandConflict('Источник или специальность уже применены другой командой. Обновите сверку.') from error
        raise
