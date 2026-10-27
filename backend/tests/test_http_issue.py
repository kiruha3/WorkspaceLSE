import pytest
from test_http_production import http_login
from test_issue_commands import ready_package, issue_values


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("category", ["1", "2"])
def test_real_http_clerk_checks_and_issues_expert_completed_material(live_server, employee_factory, grant, settings, tmp_path, category):
    settings.MEDIA_ROOT = tmp_path
    _, clerk, work, package, _, actor, _, _ = ready_package(employee_factory, grant, category=category)
    grant(actor, "issue.view", "own")
    clerk_http = http_login(live_server, clerk); expert_http = http_login(live_server, actor)
    status, body = clerk_http(f"/issue-packages/{package['id']}/check/", "POST", {"expected_version": package["version"], "reason": "ДЕМО · сверено"})
    assert status == 200; package = body["package"]
    assert expert_http(f"/issue-packages/{package['id']}/issue/", "POST", {"expected_version": package["version"], "reason": "ДЕМО · нет права", **issue_values()})[0] == 403
    status, body = clerk_http(f"/issue-packages/{package['id']}/issue/", "POST", {"expected_version": package["version"], "reason": "ДЕМО · передано получателю", **issue_values()})
    assert status == 200 and body["package"]["state"] == "issued"
    status, body = expert_http(f"/expertises/{work['id']}/issue-status/")
    assert status == 200 and body["status"] == "issued"
