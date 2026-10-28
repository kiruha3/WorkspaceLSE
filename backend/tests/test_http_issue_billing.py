import pytest
from django.core.management import call_command
from test_http_production import http_login
from test_issue_billing import prepare
from test_issue_commands import issue_values


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("category,kind,paid", [("4", "expert_conclusion", False), ("4", "expert_conclusion", True),
                                               ("6", "research_act", False), ("6", "research_act", True)])
def test_real_http_clerk_checks_and_issues_approved_result_with_paid_invoice(live_server, employee_factory, grant, category, kind, paid):
    kinds = ["expert_subscription", "cover_letter", "invoice"] if paid else ["expert_subscription", "cover_letter"]
    _, clerk, work, package, *_ = prepare(employee_factory, grant, category=category, kind=kind, paid=paid, kinds=kinds)
    call_command("seed_issue_catalogs", verbosity=0)
    http = http_login(live_server, clerk)
    status, body = http(f"/issue-packages/{package['id']}/check/", "POST", {"expected_version": package["version"], "reason": "ДЕМО · комплект сверён"})
    assert status == 200, body
    package = body["package"]
    status, body = http(f"/issue-packages/{package['id']}/issue/", "POST", {"expected_version": package["version"], "reason": "ДЕМО · передано", **issue_values()})
    assert status == 200 and body["package"]["state"] == "issued", body
    assert body["package"]["works"][0]["closure"]["result_kind"] == kind
    assert body["package"]["content"]["billing"] == [{"expertise_id": work["id"], "is_paid": paid}]
