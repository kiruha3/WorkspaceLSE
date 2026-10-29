import pytest
from django.test import Client
from apps.documents.models import Document,FileVersion
from apps.audit.models import AuditEvent
from apps.references.models import Department

pytestmark=pytest.mark.django_db


def document(owner,title='Постановление №482',kind='resolution',department=None):
    return Document.objects.create(created_by=owner,title=title,kind=kind,department=department,source_kind='paper_original')


def test_search_requires_view_and_returns_only_visible_documents(employee_factory,grant):
    actor=employee_factory();other=employee_factory()
    visible=document(actor);hidden=document(other,'Скрытое постановление')
    client=Client();client.force_login(actor.user)
    assert client.get('/api/v1/documents/').status_code==403
    grant(actor,'documents.view','own')
    before=AuditEvent.objects.count()
    response=client.get('/api/v1/documents/');assert response.status_code==200
    assert response.json()['count']==1
    assert [item['id'] for item in response.json()['results']]==[str(visible.pk)]
    assert client.get('/api/v1/documents/?search=Скрытое').json()['count']==0
    assert Document.objects.count()==2 and AuditEvent.objects.count()==before


def test_search_filters_kind_title_and_original_filename(employee_factory,grant):
    actor=employee_factory();grant(actor,'documents.view')
    first=document(actor,'Определение АБАКАН №482','decision')
    second=document(actor,'Итог №482','expert_conclusion')
    FileVersion.objects.create(document=second,number=1,file='not-opened-by-search',original_name='ЗАКЛЮЧЕНИЕ_482.pdf',content_type='application/pdf',size=1,sha256='a'*64,created_by=actor)
    client=Client();client.force_login(actor.user)
    assert client.get('/api/v1/documents/?search=абакан&kind=resolution,decision').json()['results'][0]['id']==str(first.pk)
    assert client.get('/api/v1/documents/?search=заключение_482').json()['results'][0]['id']==str(second.pk)
    assert client.get('/api/v1/documents/?search=482&kind=resolution,decision').json()['count']==1
    assert client.get('/api/v1/documents/?kind=unknown').status_code==400


def test_search_pagination_and_department_limit(employee_factory,grant):
    department=Department.objects.create(code='test',name='Тестовый отдел')
    actor=employee_factory(department=department);other=employee_factory()
    grant(actor,'documents.view','departments',departments=[department])
    for n in range(26):document(other,f'Документ {n:02}',department=department)
    document(other,'Недоступный документ')
    client=Client();client.force_login(actor.user)
    first=client.get('/api/v1/documents/').json()
    assert first['count']==26 and len(first['results'])==25 and first['next']
    second=client.get('/api/v1/documents/?page=2').json()
    assert len(second['results'])==1 and second['previous'] and second['next'] is None
    assert not ({item['id'] for item in first['results']} & {item['id'] for item in second['results']})


def test_search_includes_a_shared_basis_readable_through_own_work(employee_factory,grant):
    from test_result_completion import completion_setup
    client,actor,work,*_=completion_setup(employee_factory,grant)
    basis=Document.objects.get(pk=work['basis_document']['id'])
    assert basis.created_by_id!=actor.pk
    response=client.get('/api/v1/documents/',{'search':basis.title})
    assert response.status_code==200
    assert str(basis.pk) in {item['id'] for item in response.json()['results']}
