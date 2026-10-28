from datetime import date
from django.test import Client
from apps.intake.models import Material,Receipt
from apps.expertises import models
from apps.references.models import Department,Specialty
from apps.imports.models import ImportBatch
from apps.imports.services import persist_preview
from apps.imports.source import parse_journal
from django.utils import timezone
from journal_samples import csv_source,row


def historical_setup(employee_factory,grant,settings,tmp_path,*,state="completed",ended=date(2026,10,6),specialty_known=True,issued=None):
    settings.MEDIA_ROOT=tmp_path
    actor=employee_factory()
    for action in ("imports.preview","imports.results.view","expertise.view"):grant(actor,action)
    department=Department.objects.create(code="4",name="ДЕМО · отдел4")
    specialty=Specialty.objects.create(code="18.1",name="ДЕМО · специальность")
    content=csv_source([row(C="01.10.2026",D={"completed":"Завершена","without_execution":"Без исполнения","in_progress":"В работе","suspended":"Приостановлена"}[state],P=ended.strftime("%d.%m.%Y") if ended else "",M="18.1." if specialty_known else "")])
    stored=persist_preview(actor=actor.user,parsed=parse_journal(content,"DEMO-history.csv"),content=content,reason="ДЕМО · источник истории",source_origin="google_csv",origin_url="https://docs.google.com/spreadsheets/d/DEMO_sheet_123/edit#gid=0",source_observed_at=timezone.now())
    batch=ImportBatch.objects.get(pk=stored.receipt["batch_id"])
    material=Material.objects.create(title="ДЕМО · историческая регистрация",created_by=actor)
    arrival=Receipt.objects.create(material=material,received_at=date(2026,10,1),created_by=actor,department=department,status="historical")
    work=models.Expertise.objects.create(material=material,receipt=arrival,registration_number="151/4-1-26",sequence=151,year=2026,category_code="1",department=department,specialty=specialty if specialty_known else None,appointment_nature=None,is_commission=None,state=state,registered_by=actor.user,origin_kind="historical")
    history=models.HistoricalWork.objects.create(expertise=work,source_row=batch.rows.get(),actor=actor.user,reason="ДЕМО · подтверждён перенос",completed_on=ended if state=="completed" else None,issued_on=issued,result_kind="expert_conclusion" if state=="completed" else None,complexity_level=1,questions=2,categorical=2,probable=0,unresolved=0,executor_raw="ДЕМО · имя в журнале",authority_type="ДЕМО · тип органа")
    client=Client();client.force_login(actor.user)
    return client,actor,work,history,department,specialty
