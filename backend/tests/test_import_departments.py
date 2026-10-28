import pytest
from django.test import Client
from apps.references.models import Department
from apps.expertises.models import Expertise,ExpertAssignment
from apps.expertises.history import historical_facts
from application_samples import application_setup,selection_body,select_row,apply_rows
from journal_samples import row

pytestmark=pytest.mark.django_db


def test_historical_department1_stays1_while_employee_belongs_to4(employee_factory,grant,settings,tmp_path):
    number='151/1-1-26'
    client,_,batch,staff_department,specialty=application_setup(employee_factory,grant,settings,tmp_path,rows=[row(B=number)])
    source=batch.rows.get();raw=source.raw.copy()
    person=employee_factory(department=staff_department)
    historical=Department.objects.create(code='1',name='Отдел1 · исторический',is_active=False)
    response=client.get(f'/api/v1/imports/{batch.pk}/reconciliation/')
    item=response.json()['results'][0]
    assert item['classification']=='new' and item['blockers']==[]
    assert item['suggested_department']['id']==str(historical.pk)
    # A person's modern department must never rewrite the work's factual one.
    assert select_row(client,batch,source,selection_body(staff_department,specialty)).status_code==400
    selected=select_row(client,batch,source,selection_body(historical,specialty,employee_ids=[str(person.pk)]),key='keep-factual-department')
    assert selected.status_code==200,selected.content
    assert apply_rows(client,batch,[source]).status_code==201
    work=Expertise.objects.get()
    assert work.registration_number==number and work.department_id==historical.pk and work.receipt.department_id==historical.pk
    assert person.org_assignments.get().department_id==staff_department.pk
    assert not ExpertAssignment.objects.exists()
    source.refresh_from_db();assert source.raw==raw
    data=client.get(f'/api/v1/expertises/{work.pk}/').json()
    assert data['registration_department_code']=='1' and data['department']['code']=='1'
    facts=historical_facts(work)
    assert facts['department_code']=='1'
    item=client.get(f'/api/v1/imports/{batch.pk}/reconciliation/').json()['results'][0]
    assert item['mapped_department']['id']==str(historical.pk)
    grant(person,'expertise.view','own')
    own=Client();own.force_login(person.user)
    assert own.get(f'/api/v1/expertises/{work.pk}/').status_code==200


def test_department_scope_still_uses_factual_work_department(employee_factory,grant,settings,tmp_path):
    client,_,batch,current,specialty=application_setup(employee_factory,grant,settings,tmp_path)
    source=batch.rows.get()
    assert select_row(client,batch,source,selection_body(current,specialty)).status_code==200
    assert apply_rows(client,batch,[source]).status_code==201
    work=Expertise.objects.get();other=Department.objects.create(code='3',name='Другой текущий отдел')
    for department,expected in [(current,200),(other,403)]:
        employee=employee_factory(department=department)
        grant(employee,'expertise.view','departments',departments=[department])
        scoped=Client();scoped.force_login(employee.user)
        assert scoped.get(f'/api/v1/expertises/{work.pk}/').status_code==expected
    assert client.get(f'/api/v1/expertises/?department_id={current.pk}').json()['count']==1
    assert client.get(f'/api/v1/expertises/?department_id={other.pk}').json()['count']==0
