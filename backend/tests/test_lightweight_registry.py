from datetime import date
import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from apps.expertises.models import Expertise
from apps.intake.models import Material,Receipt
from apps.references.models import Department,Specialty

pytestmark=pytest.mark.django_db
URL='/api/v1/expertises/registry/'

@pytest.fixture
def registry(employee_factory,grant):
    actor=employee_factory();grant(actor,'expertise.view')
    department=Department.objects.create(code='4',name='Отдел 4')
    specialty=Specialty.objects.create(code='18.1',name='Стоимость')
    client=Client();client.force_login(actor.user)
    def create(number,**values):
        material=Material.objects.create(created_by=actor,title=f'Материал {number}')
        receipt=Receipt.objects.create(material=material,created_by=actor,received_at=date(2026,1,1))
        return Expertise.objects.create(material=material,receipt=receipt,registered_by=actor.user,registration_number=f'{number}/4-1-26',sequence=number,year=2026,category_code='1',department=department,specialty=specialty,appointment_nature='primary',**values)
    return client,actor,department,specialty,create

def test_full_filtered_collection_ignores_legacy_page_and_sorts_naturally(registry):
    client,actor,department,specialty,create=registry
    for number in range(1,41):create(number)
    response=client.get(URL,{'ordering':'registration_number','page':2})
    assert response.status_code==200
    data=response.json()
    assert set(data)=={'count','results'}
    assert data['count']==len(data['results'])==40
    assert [row['registration_number'] for row in data['results']]==[f'{number}/4-1-26' for number in range(1,41)]
    filtered=client.get(URL,{'search':'Материал 2','ordering':'-registration_number','department_id':str(department.id)}).json()
    assert [row['registration_number'] for row in filtered['results']]==[f'{n}/4-1-26' for n in range(29,19,-1)]+['2/4-1-26']
    assert client.get(URL,{'ordering':'unknown'}).status_code==400
    assert client.get(URL,{'received_from':'2026-03-01','received_to':'2026-01-01'}).status_code==400

def test_lightweight_contract_avoids_full_serializer_and_n_plus_one_queries(registry,monkeypatch):
    client,actor,department,specialty,create=registry
    first=create(1)
    import apps.expertises.api as api
    def reject(*args,**kwargs):raise AssertionError('Full expertise serializer must not run for the registry')
    with monkeypatch.context() as context:
        context.setattr(api,'ExpertiseOutput',reject)
        with CaptureQueriesContext(connection) as small:
            response=client.get(URL)
        assert response.status_code==200
        row=response.json()['results'][0]
        assert set(row)=={'id','origin_kind','registration_number','historical_number','receipt','material','department','specialty','current_assignments','historical','appointment_nature','is_commission','complex_group','state'}
        for number in range(2,41):create(number)
        with CaptureQueriesContext(connection) as large:
            response=client.get(URL,{'ordering':'executors'})
        assert response.status_code==200
        assert response.json()['count']==40
        assert len(large)<=len(small)+1
        assert len(large)<20
    detail=client.get(f'/api/v1/expertises/{first.pk}/').json()
    assert 'result_history' in detail and 'assignment_history' in detail and 'allowed_actions' in detail
    assert client.get('/api/v1/expertises/').json()['next'] is not None

def test_collection_keeps_department_scope_and_requires_view_right(registry,employee_factory,grant):
    client,actor,department,specialty,create=registry
    work=create(1)
    reader=employee_factory(department=department);grant(reader,'expertise.view','departments',departments=[department])
    foreign_department=Department.objects.create(code='3',name='Отдел 3')
    foreign=create(2);foreign.department=foreign_department;foreign.save(update_fields=['department'])
    client.force_login(reader.user)
    data=client.get(URL,{'ordering':'registration_number'}).json()
    assert data['count']==1 and data['results'][0]['id']==str(work.pk)
    assert client.get(URL,{'department_id':str(foreign_department.pk)}).json()['results']==[]
    denied=employee_factory();client.force_login(denied.user)
    assert client.get(URL).status_code==403

def test_projection_preserves_every_visible_field_and_calendar_filter(registry,employee_factory):
    from django.utils import timezone
    from test_journal_export import historical
    from apps.expertises.models import ExpertAssignment,HistoricalParticipant,ComplexGroup
    client,actor,department,specialty,create=registry
    work=create(1)
    history=historical(work,actor,completed_on=date(2026,1,12))
    participant=employee_factory(full_name='Исторический эксперт')
    HistoricalParticipant.objects.create(history=history,employee=participant)
    group=ComplexGroup.objects.create(material=work.material,title='Совместный материал')
    work.state='completed';work.complex_group=group;work.is_commission=True
    work.historical_number='42/10-1-25';work.save()
    current=employee_factory(full_name='Текущий эксперт')
    ExpertAssignment.objects.create(expertise=work,employee=current,actor=actor.user,started_at=timezone.now(),reason='Назначение')
    work.material.is_demo=True;work.material.save(update_fields=['is_demo'])
    response=client.get(URL,{'calendar_days_min':12,'calendar_days_max':12})
    assert response.status_code==200 and response.json()['count']==1
    light=response.json()['results'][0]
    detail=client.get(f'/api/v1/expertises/{work.pk}/').json()
    for field in ('id','origin_kind','registration_number','historical_number','appointment_nature','is_commission','state'):
        assert light[field]==detail[field]
    assert light['historical']['current_participants']==detail['historical']['current_participants']
    assert light['current_assignments']==[{'id':item['id'],'employee':item['employee']} for item in detail['current_assignments']]
    assert light['complex_group']=={'id':detail['complex_group']['id'],'title':detail['complex_group']['title']}
    for field,keys in [('receipt',['received_at']),('material',['title','is_demo']),('department',['code','name']),('specialty',['code','name'])]:
        assert light[field]=={key:detail[field][key] for key in keys}
    assert client.get(URL,{'calendar_days_min':13}).json()['count']==0
