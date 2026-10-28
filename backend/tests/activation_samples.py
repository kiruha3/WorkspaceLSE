from django.test import Client
from apps.documents.models import Document
from historical_samples import historical_setup


def activation_setup(employee_factory,grant,settings,tmp_path,**overrides):
    client,actor,work,history,department,specialty=historical_setup(employee_factory,grant,settings,tmp_path,**overrides)
    for code in ('imports.history.activate','expertise.register','documents.view','documents.upload'):grant(actor,code)
    basis=Document.objects.create(kind='resolution',title='ДЕМО · подтверждённое постановление',source_kind='paper_original',created_by=actor,department=department)
    return client,actor,work,history,department,specialty,basis


def activation_body(basis,specialty,**overrides):
    return {'expected_version':1,'reason':'ДЕМО · сверено по настоящему документу','basis_document_id':str(basis.pk),'specialty_id':str(specialty.pk) if specialty else None,
        'appointment_nature':'primary','is_commission':False,'complex_known':True,'complex_group_id':None,'suspension_history_complete':False,'past_suspensions':[],'suspended_on':None,**overrides}


def activate(client,work,body,key='activate-history'):
    return client.post(f'/api/v1/expertises/{work.pk}/activate-history/',body,content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)


def evidence(client,actor,kind):
    from test_basis_documents import upload
    document=Document.objects.create(kind=kind,title='ДЕМО · фактический итог',source_kind='uploaded_copy',created_by=actor)
    response=upload(client,str(document.pk));assert response.status_code==201
    return document
