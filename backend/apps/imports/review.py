"""Exact proposals and atomic, explicitly selected source changes."""
from collections import Counter
import hashlib
import json
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import CommandConflict,execute_once
from apps.accounts.services import audit
from apps.expertises.models import Expertise
from apps.intake.models import Material,Receipt
from apps.personnel.models import Employee
from apps.references.models import Department,Specialty
from .application import apply_selection,application_data,lock_numbers,require_apply
from .models import ImportBatch,ImportRow,ImportApplication,ImportSelection
from .reconciliation import ReconciliationContext,classify_row,selection_data,save_selection,require_reconcile,validate_mapping
from .reconciliation_serializers import SelectionInput
from .updates import apply_updates,update_preview,source_values

MAPPING_FIELDS=('department_id','specialty_id','employee_ids','appointment_nature','is_commission','complex_known','complex_group_key','statistics_confirmed')


def proposal(row,context=None,people=None):
    context=context or ReconciliationContext.for_rows([row])
    people=list(Employee.objects.all()) if people is None else people
    classified=classify_row(row,context)
    work=context.works.get(row.facts.get('registration_number'))
    previous=getattr(getattr(work,'historical',None),'source_row',None)
    previous_choice=selection_data(getattr(previous,'selection',None)) if previous else None
    saved=selection_data(getattr(row,'selection',None))
    choice={key:saved[key] for key in MAPPING_FIELDS} if saved else {
        'department_id':str(ref.pk) if (ref:=context.departments.get(row.facts.get('department_code'))) else None,
        'specialty_id':str(ref.pk) if (ref:=context.specialties.get(row.facts.get('specialty_code'))) else None,
        'employee_ids':[], 'appointment_nature':None,'is_commission':None,'complex_known':False,
        'complex_group_key':None,'statistics_confirmed':False}
    blockers=[item['message'] for item in classified['blockers']]
    if not saved:
        if previous_choice:
            for key in ('appointment_nature','is_commission','complex_known','complex_group_key','statistics_confirmed'):
                choice[key]=previous_choice[key]
        raw=row.facts.get('executor_raw','').strip()
        if previous_choice and raw==previous.facts.get('executor_raw','').strip():
            choice['employee_ids']=previous_choice['employee_ids']
        elif raw:
            matches=[person for person in people if ' '.join(person.full_name.split())==' '.join(raw.split())]
            if len(matches)==1:choice['employee_ids']=[str(matches[0].pk)]
            else:blockers.append('Исполнитель не сопоставлен однозначно. Откройте подробную сверку и выберите сотрудников.')
        if row.facts.get('specialty_code') and choice['specialty_id'] is None:
            blockers.append('Кода специальности нет в справочнике. Требуется сопоставление.')
        if row.raw.get('M') and not row.facts.get('specialty_code'):
            blockers.append('Непустой код специальности не распознан. Требуется подробная сверка.')
    if choice['department_id'] is None:blockers.append('Фактический отдел не сопоставлен.')
    elif classified['classification']!='invalid':
        try:
            validate_mapping(row,next(ref for ref in context.departments.values() if str(ref.pk)==choice['department_id']),
                next((ref for ref in context.specialties.values() if str(ref.pk)==choice['specialty_id']),None),choice['statistics_confirmed'])
        except (ValidationError,StopIteration):blockers.append('Сопоставление требует проверки в подробной сверке.')
    info={'row_id':str(row.pk),'source_row':row.source_row,'number':row.facts.get('registration_number') or row.raw.get('B') or '',
          'classification':classified['classification'],'action':'update' if work else 'create',
          'expected_work_version':work.version if work else None,'expected_source_row_id':str(previous.pk) if previous else None,
          'expected_selection_version':saved['version'] if saved else 0,'selection':choice,
          'work_id':str(work.pk) if work else None,'blockers':blockers,'changes':[],
          'diagnostics':row.diagnostics}
    if work and previous_choice and classified['classification']=='changed':
        preview=update_preview(row,work,selective=True,proposed_selection=choice)
        blockers.extend(preview['blockers']);info['changes']=preview['changes']
    elif work:
        blockers.append('Нет изменений источника либо подтверждённой базы прежнего переноса.')
    elif not blockers:
        values=source_values(row,choice)
        info['changes']=[{'field':field,'before':None,'after':value,'conflict':False} for field,value in values.items()
            if value is not None and value!='' and value!=[]]
        for change in info['changes']:
            if change['field'] in ('department_id','specialty_id'):
                refs=context.departments if change['field']=='department_id' else context.specialties
                ref=next((r for r in refs.values() if str(r.pk)==change['after']),None)
                change['after_label']=f'{ref.code} · {ref.name}' if ref else 'Не заполнено'
            if change['field']=='employee_ids':
                change['after_label']=', '.join(person.full_name for person in people if str(person.pk) in change['after'])
    info['eligible']=not blockers
    info['proposal_hash']=hashlib.sha256(json.dumps(info,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return info


def review_batch(batch):
    rows=list(batch.rows.select_related('selection').prefetch_related('selection__employees'))
    context=ReconciliationContext.for_rows(rows);people=list(Employee.objects.all().order_by('pk'))
    summary=Counter(classify_row(row,context)['classification'] for row in rows)
    return {'batch_id':str(batch.pk),'summary':{key:summary[key] for key in ('new','changed','unchanged','invalid')},
            'results':[proposal(row,context,people) for row in rows if classify_row(row,context)['classification']!='unchanged']}


@transaction.atomic
def apply_review(*,actor,batch_id,selections,key,payload):
    require_apply(actor);require_reconcile(actor)
    batch=get_object_or_404(ImportBatch,pk=batch_id)
    rows=list(batch.rows.filter(pk__in=[entry['row_id'] for entry in selections]).order_by('pk'))
    if len(rows)!=len(selections):raise ValidationError({'selections':'Все выбранные строки должны принадлежать этому снимку.'})
    lock_numbers([row.facts.get('registration_number') or '' for row in rows])
    def operation():
        # Match the established material/receipt/work/row/reference lock order.
        ImportBatch.objects.select_for_update().get(pk=batch.pk)
        anchors=list(Expertise.objects.filter(registration_number__in=[r.facts.get('registration_number') for r in rows]).values('id','material_id','receipt_id'))
        list(Material.objects.select_for_update().filter(pk__in={a['material_id'] for a in anchors}).order_by('pk'))
        list(Receipt.objects.select_for_update().filter(pk__in={a['receipt_id'] for a in anchors}).order_by('pk'))
        list(Expertise.objects.select_for_update().filter(pk__in={a['id'] for a in anchors}).order_by('pk'))
        locked=list(ImportRow.objects.select_for_update().filter(pk__in=[r.pk for r in rows]).order_by('pk'))
        list(ImportSelection.objects.select_for_update().filter(row_id__in=[r.pk for r in locked]).order_by('pk'))
        list(Department.objects.select_for_update().order_by('pk'))
        list(Specialty.objects.select_for_update().order_by('pk'))
        people=list(Employee.objects.select_for_update().order_by('pk'))
        context=ReconciliationContext.for_rows(locked)
        expected={entry['row_id']:entry for entry in selections};plans=[]
        for row in locked:
            info=proposal(row,context,people);entry=expected[row.pk]
            for field in ('action','expected_work_version','expected_source_row_id','expected_selection_version','proposal_hash'):
                if str(info[field])!=str(entry[field]):raise CommandConflict('Перечень изменился. Обновите данные и выберите изменения заново.')
            if not info['eligible']:raise CommandConflict(' '.join(info['blockers']))
            fields=entry['accepted_fields']
            if info['action']=='update' and (not fields or not set(fields)<={c['field'] for c in info['changes']}):
                raise ValidationError({'accepted_fields':'Выберите только показанные изменённые поля.'})
            if info['action']=='create' and fields:raise ValidationError({'accepted_fields':'Новая экспертиза добавляется целиком.'})
            plans.append((row,info,entry))
        reason='Обновление БД: пользователь проверил перечень и явно выбрал принимаемые изменения.'
        create=[];updates=[]
        def child_key(label):return hashlib.sha256((key+':'+label).encode()).hexdigest()
        for row,info,entry in plans:
            body={'expected_version':info['expected_selection_version'],'reason':reason,**info['selection']}
            form=SelectionInput(data=body);form.is_valid(raise_exception=True)
            save_selection(actor=actor,row_id=row.pk,data=form.validated_data,key=child_key(str(row.pk)),payload=body)
            version=ImportSelection.objects.get(row=row).version
            if info['action']=='create':create.append({'row_id':row.pk,'expected_selection_version':version})
            else:updates.append({'row_id':row.pk,'expected_selection_version':version,'expected_work_version':entry['expected_work_version'],
                                 'expected_source_row_id':entry['expected_source_row_id'],'accepted_fields':entry['accepted_fields']})
        applications=[]
        for label,items,operation_fn in (('create',create,apply_selection),('update',updates,apply_updates)):
            if not items:continue
            body={'reason':reason,'selections' if label=='create' else 'updates':items}
            result=operation_fn(actor=actor,batch_id=batch.pk,key=child_key(label),payload=body,**body)
            applications.append(application_data(ImportApplication.objects.get(pk=result['application_id'])))
        result={'batch_id':str(batch.pk),'created_count':len(create),'updated_count':len(updates),'applications':applications}
        event=audit(actor,'imports.sync',batch,result,reason)
        return {'event':{'id':str(event.pk)},**result}
    return execute_once(actor=actor,action='imports.sync',key=key,payload=payload,operation=operation)
