from django.test import Client
from apps.imports.services import persist_preview
from apps.imports.source import parse_journal
from apps.imports.models import ImportBatch
from apps.references.models import Department,Specialty
from journal_samples import csv_source,row


def application_setup(employee_factory,grant,settings,tmp_path,rows=None):
    settings.MEDIA_ROOT=tmp_path
    actor=employee_factory()
    for code in ("imports.preview","imports.results.view","imports.reconcile","imports.apply","expertise.view"):
        grant(actor,code)
    department=Department.objects.create(code="4",name="ДЕМО · отдел4")
    specialty=Specialty.objects.create(code="18.1",name="ДЕМО · специальность")
    client=Client();client.force_login(actor.user)
    batch=source_batch(actor,rows or [row(Q="2",R="2",S="0",T="0")])
    return client,actor,batch,department,specialty


def source_batch(actor,rows):
    content=csv_source(rows)
    stored=persist_preview(actor=actor.user,parsed=parse_journal(content,"DEMO-application.csv"),content=content,reason="ДЕМО · источник")
    return ImportBatch.objects.get(pk=stored.receipt["batch_id"])


def selection_body(department,specialty,**overrides):
    return {"expected_version":0,"reason":"ДЕМО · подтверждено ответственным", "department_id":str(department.pk),"specialty_id":str(specialty.pk) if specialty else None,
        "employee_ids":[],"appointment_nature":None,"is_commission":None,"complex_known":False,"complex_group_key":None,"statistics_confirmed":False,**overrides}


def select_row(client,batch,source,body,key="select-row"):
    return client.put(f"/api/v1/imports/{batch.pk}/rows/{source.pk}/selection/",body,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)


def apply_rows(client,batch,sources,key="apply-rows",**overrides):
    body={"reason":"ДЕМО · применить подтверждённый пакет","selections":[{"row_id":str(source.pk),"expected_selection_version":1} for source in sources],**overrides}
    return client.post(f"/api/v1/imports/{batch.pk}/apply/",body,content_type="application/json",HTTP_IDEMPOTENCY_KEY=key)
