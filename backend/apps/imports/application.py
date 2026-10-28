import hashlib
from datetime import date
from django.db import transaction,connection,IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.policies import require,active_employee
from apps.accounts.services import audit,check_version
from apps.expertises.history import FIELDS
from apps.expertises.models import Expertise,ComplexGroup,HistoricalWork,HistoricalParticipant
from apps.intake.models import Material,Receipt
from apps.intake.locking import require_not_issued
from apps.personnel.models import Employee
from apps.references.models import Department,Specialty
from .models import ImportBatch,ImportSelection,ImportApplication,ImportApplicationItem
from .policies import require_preview_read
from .reconciliation import identity_blockers,validate_mapping


def require_apply(actor):
    require_preview_read(actor)
    require(actor,"imports.apply")


def application_data(application):
    return {"id":str(application.pk),"batch_id":str(application.batch_id),"created_at":application.created_at,
        "created_count":sum(item["action"]=="created" for item in application.links),
        "existing_count":sum(item["action"]=="existing" for item in application.links),
        "updated_count":sum(item["action"]=="updated" for item in application.links),"items":application.links}


def lock_numbers(numbers):
    locks={int.from_bytes(hashlib.blake2b(("ais-journal-number:"+number).encode(),digest_size=8).digest(),"big",signed=True) for number in numbers}
    with connection.cursor() as cursor:
        for lock in sorted(locks):cursor.execute("SELECT pg_advisory_xact_lock(%s)",[lock])


def source_facts(row,*,as_of=None):
    """Do not promote contradictory source values to trusted typed facts."""
    values={field:row.facts.get(field) for field in FIELDS}
    codes={item["code"] for item in row.diagnostics}
    if "date_order" in codes:values["completed_on"]=None
    if "work_family_conflict" in codes:values["result_kind"]=None
    for field in ("completed_on","return_decided_on","issued_on"):
        parsed=date.fromisoformat(values[field]) if values[field] else None
        received=date.fromisoformat(row.facts["received_on"])
        values[field]=parsed if parsed and received<=parsed<=(as_of or timezone.localdate()) else None
    return values


def _apply_selection(*,actor,batch_id,selections,reason,key,payload):
    with transaction.atomic():
        require_apply(actor)
        row_ids=[item["row_id"] for item in selections]
        # Fixed number locks precede batch/row/reference locks for all packets.
        batch=get_object_or_404(ImportBatch,pk=batch_id)
        source_rows=list(batch.rows.filter(pk__in=row_ids))
        if len(source_rows)!=len(row_ids):raise ValidationError({"selections":"Все строки должны принадлежать выбранному снимку."})
        lock_numbers([row.facts["registration_number"] for row in source_rows if row.facts.get("registration_number")])
        batch=ImportBatch.objects.select_for_update().get(pk=batch.pk)
        rows=list(batch.rows.select_for_update().filter(pk__in=row_ids).order_by("pk"))
        selected=list(ImportSelection.objects.select_for_update().filter(row_id__in=row_ids).order_by("row_id"))
        by_row={item.row_id:item for item in selected}
        expected={item["row_id"]:item["expected_selection_version"] for item in selections}

        def operation():
            require_apply(actor)
            if len(selected)!=len(rows):raise ValidationError({"selections":"Сначала явно сохраните сопоставление каждой строки."})
            previous={item.row_id:item for item in ImportApplicationItem.objects.filter(row_id__in=row_ids).select_related("work")}
            group_keys={item.complex_group_key for item in selected if item.row_id not in previous and item.complex_group_key}
            prior_groups={}
            for item in ImportApplicationItem.objects.filter(row__batch=batch,row__selection__complex_group_key__in=group_keys).select_related("row__selection","work__complex_group"):
                if item.work.complex_group is None:raise CommandConflict("Ранее применённый состав комплекса изменился; требуется отдельная сверка.")
                prior_groups[item.row.selection.complex_group_key]=item.work.complex_group
            # Native issuance/activation also lock Material before references.
            # Lock all reused materials in a fixed order, then recheck issuance.
            material_ids={group.material_id for group in prior_groups.values()}
            for material in Material.objects.select_for_update().filter(pk__in=material_ids).order_by("pk"):
                require_not_issued(material.pk)
            departments={ref.pk:ref for ref in Department.objects.select_for_update().filter(pk__in=[item.department_id for item in selected]).order_by("pk")}
            specialties={ref.pk:ref for ref in Specialty.objects.select_for_update().filter(pk__in=[item.specialty_id for item in selected if item.specialty_id]).order_by("pk")}
            employee_ids=set(ImportSelection.employees.through.objects.filter(importselection_id__in=[item.pk for item in selected]).values_list("employee_id",flat=True))
            employees={person.pk:person for person in Employee.objects.select_for_update().filter(pk__in=employee_ids).order_by("pk")}
            existing={work.registration_number:work for work in Expertise.objects.filter(registration_number__in=[row.facts.get("registration_number") for row in rows])}
            for row in rows:
                selection=by_row[row.pk];check_version(selection,expected[row.pk])
                validate_mapping(row,departments[selection.department_id],specialties.get(selection.specialty_id),selection.statistics_confirmed)
                if identity_blockers(row):raise ValidationError({"selections":f"Строка {row.source_row}: уточните номер, поступление или состояние в источнике."})
                if row.pk not in previous and row.facts["registration_number"] in existing:
                    raise CommandConflict(f"Номер {row.facts['registration_number']} уже есть в основном реестре. Автоматическое обновление из нового снимка не выполняется.")
                if selection.complex_group_key and selection.specialty_id is None:raise ValidationError({"selections":"Для явного комплекса нужно уточнить специальность каждой работы."})
            employee=active_employee(actor)
            application=ImportApplication.objects.create(batch=batch,actor=actor,reason=reason)
            groups={};links=[]
            for row in rows:
                if row.pk in previous:
                    links.append({"row_id":str(row.pk),"expertise_id":str(previous[row.pk].work_id),"action":"existing"});continue
                selection=by_row[row.pk];facts=row.facts;group=None
                if selection.complex_group_key:
                    group=groups.get(selection.complex_group_key)
                    if group is None:
                        prior=prior_groups.get(selection.complex_group_key)
                        if prior:group=prior
                        else:
                            material=Material.objects.create(title=f"Исторический комплекс {selection.complex_group_key}",created_by=employee)
                            group=ComplexGroup.objects.create(material=material,title=selection.complex_group_key)
                        groups[selection.complex_group_key]=group
                    material=group.material
                    if Expertise.objects.filter(complex_group=group,specialty_id=selection.specialty_id).exists():raise CommandConflict("В комплексе уже есть работа этой специальности.")
                else:material=Material.objects.create(title=f"Историческая регистрация {facts['registration_number']}",created_by=employee)
                receipt=Receipt.objects.create(material=material,received_at=date.fromisoformat(facts["received_on"]),sender_name=facts.get("authority_name","")[:500],department_id=selection.department_id,created_by=employee,status="historical")
                work=Expertise.objects.create(receipt=receipt,material=material,registration_number=facts["registration_number"],historical_number=facts.get("historical_number") or "",
                    sequence=facts["sequence"],year=facts["year"],category_code=facts["category_code"],department_id=selection.department_id,specialty_id=selection.specialty_id,
                    appointment_nature=selection.appointment_nature,is_commission=selection.is_commission,complex_group=group,state=facts["state"],origin_kind="historical",registered_by=actor)
                history=HistoricalWork.objects.create(expertise=work,source_row=row,actor=actor,reason=reason,complex_known=selection.complex_known,statistics_confirmed=selection.statistics_confirmed,**source_facts(row))
                HistoricalParticipant.objects.bulk_create([HistoricalParticipant(history=history,employee=employees[person.pk]) for person in selection.employees.all()])
                ImportApplicationItem.objects.create(application=application,row=row,work=work)
                links.append({"row_id":str(row.pk),"expertise_id":str(work.pk),"action":"created"})
            application.links=links;application.save(update_fields=["links"])
            event=audit(actor,"imports.apply",application,{"batch_id":str(batch.pk),"items":links},reason)
            return {"id":str(event.pk),"application_id":str(application.pk)}
        return execute_once(actor=actor,action="imports.apply",key=key,payload={"batch_id":str(batch.pk),"data":payload},operation=operation)


def apply_selection(**kwargs):
    try:return _apply_selection(**kwargs)
    except IntegrityError as error:
        if getattr(error.__cause__,"sqlstate",None)=="23505":raise CommandConflict("Номер, исходная строка или специальность комплекса уже применены другой командой. Обновите сверку.") from error
        raise
