from datetime import date
import pytest
from historical_samples import historical_setup

pytestmark=pytest.mark.django_db


@pytest.mark.parametrize('issued',[None,date(2026,10,7)])
def test_issue_status_names_historical_origin_without_inventing_new_package(employee_factory,grant,settings,tmp_path,issued):
    client,actor,work,_,_,_=historical_setup(employee_factory,grant,settings,tmp_path,issued=issued)
    grant(actor,'issue.view')
    response=client.get(f'/api/v1/expertises/{work.pk}/issue-status/')
    assert response.status_code==200
    assert response.json()=={'status':'issued' if issued else 'not_issued','issued_on':issued.isoformat() if issued else None,'fact_origin':'historical','package':None}
    from apps.issuance.models import MaterialIssue,IssuePackage
    assert not MaterialIssue.objects.exists() and not IssuePackage.objects.exists()
