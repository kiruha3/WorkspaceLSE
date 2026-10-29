from datetime import date
import uuid
import pytest
from apps.audit.models import AuditEvent
from apps.expertises.models import Expertise, Suspension
from apps.expertises.journal_export import journal_values
from historical_samples import historical_setup
from test_result_completion import completion_setup, ready_result, send
from test_form151_registry import calculate
from test_form151 import value

pytestmark=pytest.mark.django_db


def completed(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,*_=completion_setup(employee_factory,grant)
    work=ready_result(client,work)
    done=send(client,work,'complete',result_id=work['result']['id'])
    assert done.status_code==200
    return client,actor,done.json()['expertise']


def test_reopen_requires_permission_reason_and_current_version(employee_factory,grant,settings,tmp_path):
    client,actor,work=completed(employee_factory,grant,settings,tmp_path)
    assert send(client,work,'reopen',reason='Ошибочное завершение').status_code==403
    grant(actor,'expertise.reopen','own')
    detail=client.get(f"/api/v1/expertises/{work['id']}/").json()
    assert 'expertise.reopen' in detail['allowed_actions']
    assert send(client,work,'reopen',reason=' ').status_code==400
    assert send(client,work,'reopen',expected_version=work['version']-1).status_code==409
    assert not AuditEvent.objects.filter(action='expertise.reopen').exists()


def test_reopen_preserves_history_and_recompletion_increments_closure(employee_factory,grant,settings,tmp_path):
    client,actor,work=completed(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.reopen','own');key=str(uuid.uuid4())
    response=send(client,work,'reopen',key=key,reason='Случайно завершена')
    assert response.status_code==200,response.content
    opened=response.json()['expertise']
    assert opened['state']=='in_progress' and opened['version']==work['version']+1
    assert opened['closure'] is None and opened['closure_history']==work['closure_history']
    assert opened['result_history']==work['result_history']
    assert opened['current_assignments']==work['current_assignments']
    assert opened['registration_number']==work['registration_number']
    event=opened['reopening_history'][0]
    assert event['closure_id']==work['closure']['id'] and event['reason']=='Случайно завершена'
    assert event['actor']['id']==str(actor.user_id)
    assert send(client,opened,'reopen').status_code==400
    assert send(client,work,'reopen',key=key,reason='Случайно завершена').status_code==200
    assert AuditEvent.objects.filter(action='expertise.reopen').count()==1
    again=send(client,opened,'complete',result_id=opened['result']['id'])
    assert again.status_code==200,again.content
    assert again.json()['expertise']['closure']['number']==2
    # Replaying an old successful command must not reopen a newly completed work.
    replay=send(client,work,'reopen',key=key,reason='Случайно завершена')
    assert replay.json()['expertise']['state']=='completed'
    assert len(replay.json()['expertise']['reopening_history'])==1


def test_historical_reopen_keeps_source_but_clears_current_end_and_report(employee_factory,grant,settings,tmp_path):
    client,actor,work,history,*_=historical_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.reopen')
    raw=history.source_row.raw.copy();facts=history.source_row.facts.copy()
    assert value(calculate(),1,'J108')==1
    response=send(client,{'id':str(work.pk),'version':work.version},'reopen')
    assert response.status_code==200,response.content
    opened=response.json()['expertise'];history.refresh_from_db();work.refresh_from_db()
    assert history.completed_on is None and history.return_decided_on is None and not history.operational
    assert opened['reopening_history'][0]['historical_completed_on']=='2026-10-06'
    assert not work.assignments.exists() and work.receipt.basis_document_id is None
    history.source_row.refresh_from_db()
    assert history.source_row.raw==raw and history.source_row.facts==facts
    report=calculate()
    assert value(report,1,'J108')==0 and value(report,1,'Q108')==1
    assert not any(str(work.pk) in g['rows'] for g in report['gaps'] if g['code']=='unaccepted_end')
    assert journal_values(work,1,date(2026,10,29))[15] is None


def test_native_reopen_does_not_count_retired_closure_or_export_end(employee_factory,grant,settings,tmp_path):
    client,actor,work=completed(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.reopen','own')
    response=send(client,work,'reopen');assert response.status_code==200
    report=calculate()
    assert value(report,1,'J108')==0 and value(report,1,'Q108')==1
    assert not any(g['code']=='unaccepted_end' for g in report['gaps'])
    assert journal_values(Expertise.objects.get(pk=work['id']),1,date(2026,10,29))[15] is None


def test_reopen_preserves_existing_open_suspension(employee_factory,grant,settings,tmp_path):
    client,actor,work=completed(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.reopen','own')
    pause=Suspension.objects.create(expertise_id=work['id'],suspended_on=date(2026,10,5),reason='Нужны материалы',actor=actor.user)
    response=send(client,work,'reopen');assert response.status_code==200
    assert response.json()['expertise']['state']=='suspended'
    pause.refresh_from_db();assert pause.resumed_on is None


@pytest.mark.parametrize('state,issued',[('completed',date(2026,10,8)),('without_execution',None),('in_progress',None)])
def test_reopen_rejects_issued_or_non_completed_history(employee_factory,grant,settings,tmp_path,state,issued):
    client,actor,work,history,*_=historical_setup(employee_factory,grant,settings,tmp_path,state=state,issued=issued)
    grant(actor,'expertise.reopen')
    body={'id':str(work.pk),'version':work.version}
    assert send(client,body,'reopen').status_code==400
    detail=client.get(f'/api/v1/expertises/{work.pk}/').json()
    assert 'expertise.reopen' not in detail['allowed_actions']
    work.refresh_from_db();assert work.state==state and work.version==1


def test_reopen_invalidates_checked_issue_and_cannot_undo_actual_issue(employee_factory,grant,settings,tmp_path):
    from test_issue_commands import ready_package,checked,package_command,issue_values
    settings.MEDIA_ROOT=tmp_path
    client,clerk,work,package,expert,actor,*_=ready_package(employee_factory,grant)
    grant(actor,'expertise.reopen','own')
    package=checked(client,package)
    response=send(expert,work,'reopen');assert response.status_code==200
    assert package_command(client,package,'issue',**issue_values()).status_code==400
    opened=response.json()['expertise']
    done=send(expert,opened,'complete',result_id=opened['result']['id']).json()['expertise']
    assert package_command(client,package,'issue',**issue_values()).status_code==400
    package=checked(client,package)
    assert package_command(client,package,'issue',**issue_values()).status_code==200
    assert send(expert,done,'reopen').status_code==400


def test_reopen_rechecks_revoked_permission_and_scopes(employee_factory,grant,settings,tmp_path):
    from django.test import Client
    client,actor,work=completed(employee_factory,grant,settings,tmp_path)
    role,assignment=grant(actor,'expertise.reopen','own')
    opened=send(client,work,'reopen',key='revoke-test');assert opened.status_code==200
    assignment.is_active=False;assignment.save()
    assert send(client,work,'reopen',key='revoke-test').status_code==403
    outsider=employee_factory();grant(outsider,'expertise.view');grant(outsider,'expertise.reopen','own')
    other=Client();other.force_login(outsider.user)
    assert send(other,opened.json()['expertise'],'reopen').status_code==403


def test_reopened_history_cannot_be_overwritten_by_import(employee_factory,grant,settings,tmp_path):
    from apps.imports.updates import update_preview
    client,actor,work,history,*_=historical_setup(employee_factory,grant,settings,tmp_path)
    grant(actor,'expertise.reopen')
    assert send(client,{'id':str(work.pk),'version':work.version},'reopen').status_code==200
    work.refresh_from_db()
    # A real import has a prior selection. This fixture stops before that; the
    # explicit reopening guard must already reject it, even in selective mode.
    result=update_preview(history.source_row,work,selective=True)
    assert not result['eligible']
    assert any('возврат' in item.lower() for item in result['blockers'])


def test_own_reopen_includes_current_historical_participant(employee_factory,grant,settings,tmp_path):
    from apps.expertises.models import HistoricalParticipant
    from django.test import Client
    client,actor,work,history,*_=historical_setup(employee_factory,grant,settings,tmp_path)
    owner=employee_factory();HistoricalParticipant.objects.create(history=history,employee=owner)
    grant(owner,'expertise.view','own');grant(owner,'expertise.reopen','own')
    client=Client();client.force_login(owner.user)
    detail=client.get(f'/api/v1/expertises/{work.pk}/');assert detail.status_code==200
    assert 'expertise.reopen' in detail.json()['allowed_actions']
    assert send(client,detail.json(),'reopen').status_code==200
