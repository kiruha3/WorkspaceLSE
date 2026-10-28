"""Paid work is an explicit revision fact, not a category/amount guess."""
import uuid
import pytest
from django.core.management import call_command
from apps.accounts.models import CommandReceipt
from apps.audit.models import AuditEvent
from apps.issuance.models import IssuePackage, PackageRevision, MaterialIssue
from test_issue_drafts import issue_setup, package_items, save_package
from test_issue_commands import checked, package_command, issue_values
from test_registration import register

pytestmark = pytest.mark.django_db


def prepare(employee_factory, grant, *, category="4", kind="expert_conclusion", paid=False, kinds=None):
    client, clerk, work, expert, actor, department, specialty = issue_setup(
        employee_factory, grant, completed=True, category=category, kind=kind)
    items = package_items(client, work, kinds or ["expert_subscription", "cover_letter"])
    body = {"materials_description": "ДЕМО · два тома", "items": items,
            "billing": [{"expertise_id": work["id"], "is_paid": paid}], "reason": "ДЕМО · платность указана явно"}
    if paid == "omitted": body.pop("billing")
    elif paid == "empty": body["billing"] = []
    response = client.post(f"/api/v1/materials/{work['material']['id']}/issue-packages/", body,
                          content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 201, response.content
    return client, clerk, work, response.json()["package"], expert, actor, department, specialty, items


@pytest.mark.parametrize("category,kind,paid,want", [
    ("4", "expert_conclusion", False, ["expert_subscription", "cover_letter"]),
    ("4", "expert_conclusion", True, ["expert_subscription", "cover_letter", "invoice"]),
    ("6", "research_act", False, ["expert_subscription", "cover_letter"]),
    ("6", "research_act", True, ["expert_subscription", "cover_letter", "invoice"]),
    ("1", "expert_conclusion", True, ["expert_subscription", "cover_letter", "notification", "invoice"]),
    ("5", "expert_conclusion", True, ["expert_subscription", "cover_letter", "notification", "invoice"]),
    ("2", "expert_conclusion", True, ["expert_subscription", "cover_letter", "invoice"]),
    ("3", "expert_conclusion", True, ["expert_subscription", "cover_letter", "invoice"]),
])
def test_approved_pack_and_paid_invoice_are_enforced(employee_factory, grant, category, kind, paid, want):
    client, _, work, package, *_ = prepare(employee_factory, grant, category=category, kind=kind, paid=paid, kinds=want)
    assert package["works"][0]["is_paid"] is paid
    assert package["works"][0]["required_items"] == want
    assert package["readiness"]["can_check"] and package["readiness"]["blockers"] == []
    assert package_command(client, package, "check").status_code == 200
    if "invoice" in want:
        items = [{"kind": item["kind"], "expertise_id": work["id"], "document_id": item["document"]["id"]}
                 for item in package["content"]["items"] if item["kind"] != "invoice"]
        # Check incremented the package version; use the current response.
        current = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
        missing = save_package(client, current, materials_description="Два тома", items=items).json()["package"]
        assert any(item["code"] == "item_missing" and item["field"] == "invoice" for item in missing["readiness"]["blockers"])
        assert not missing["readiness"]["can_check"]


@pytest.mark.parametrize("paid", [None, "omitted", "empty"])
def test_unknown_payability_is_not_free_even_if_all_documents_exist(employee_factory, grant, paid):
    client, _, _, package, *_ = prepare(employee_factory, grant, paid=paid, kinds=["expert_subscription", "cover_letter", "invoice"])
    assert package["works"][0]["is_paid"] is None
    assert any(item["code"] == "billing_unknown" for item in package["readiness"]["blockers"])
    assert package_command(client, package, "check").status_code == 400
    assert not package["readiness"]["can_check"] and not package["readiness"]["can_issue"]
    assert not AuditEvent.objects.filter(action="issue.check").exists()


def test_billing_revisions_preserve_omitted_values_and_explicit_null_clears(employee_factory, grant):
    client, _, work, package, *_, items = prepare(employee_factory, grant, paid=True)
    original = package["content"]
    for changes in ({}, {"billing": []}):
        package = save_package(client, package, materials_description="Два тома", items=items, **changes).json()["package"]
        assert package["works"][0]["is_paid"] is True
        assert package["content"]["billing"] == [{"expertise_id": work["id"], "is_paid": True}]
    key = str(uuid.uuid4())
    response = save_package(client, package, key=key, materials_description="Два тома", items=items,
                            billing=[{"expertise_id": work["id"], "is_paid": None}])
    assert response.status_code == 200
    current = response.json()["package"]
    assert current["works"][0]["is_paid"] is None
    assert current["content_history"][0] == original
    assert len(current["content_history"]) == 4
    replay = save_package(client, package, key=key, materials_description="Два тома", items=items,
                          billing=[{"expertise_id": work["id"], "is_paid": None}])
    assert replay.status_code == 200 and replay.json()["event"] == response.json()["event"]
    assert PackageRevision.objects.count() == 4


def test_paid_change_expires_check_and_missing_invoice_cannot_be_issued(employee_factory, grant):
    client, _, work, package, *_, items = prepare(employee_factory, grant)
    call_command("seed_issue_catalogs", verbosity=0)
    package = checked(client, package)
    changed = save_package(client, package, materials_description="Два тома", items=items,
                           billing=[{"expertise_id": work["id"], "is_paid": True}])
    assert changed.status_code == 200
    package = changed.json()["package"]
    assert package["state"] == "needs_recheck" and not package["readiness"]["check_current"]
    assert package_command(client, package, "issue", **issue_values()).status_code == 400
    assert not MaterialIssue.objects.exists()
    items += package_items(client, work, ["invoice"])
    package = save_package(client, package, materials_description="Два тома", items=items).json()["package"]
    assert package["readiness"]["can_check"] and not package["readiness"]["can_issue"]
    assert package_command(client, package, "issue", **issue_values()).status_code == 400
    package = checked(client, package)
    assert package_command(client, package, "issue", **issue_values()).status_code == 200


@pytest.mark.parametrize("variant", ["duplicate", "foreign", "invalid", "extra"])
def test_invalid_billing_never_appends_partial_draft_or_receipt(employee_factory, grant, variant):
    client, _, work, package, *_ = prepare(employee_factory, grant)
    item = {"expertise_id": work["id"], "is_paid": True}
    billing = [item]
    if variant == "duplicate": billing += [item.copy()]
    if variant == "foreign": billing[0] = {**item, "expertise_id": str(uuid.uuid4())}
    if variant == "invalid": billing[0] = {**item, "is_paid": "maybe"}
    if variant == "extra": billing[0] = {**item, "amount": 100}
    before = (PackageRevision.objects.count(), AuditEvent.objects.count(), CommandReceipt.objects.count())
    key = str(uuid.uuid4())
    assert save_package(client, package, key=key, billing=billing).status_code == 400
    assert before == (PackageRevision.objects.count(), AuditEvent.objects.count(), CommandReceipt.objects.count())
    assert IssuePackage.objects.get(pk=package["id"]).version == package["version"]
    assert not CommandReceipt.objects.filter(key=key).exists()


@pytest.mark.parametrize("variant", ["duplicate", "foreign", "missing_flag"])
def test_invalid_initial_billing_does_not_leave_an_orphan_package(employee_factory, grant, variant):
    client, _, work, *_ = issue_setup(employee_factory, grant)
    billing = [{"expertise_id": work["id"], "is_paid": True}]
    if variant == "duplicate": billing += [billing[0].copy()]
    elif variant == "foreign": billing[0]["expertise_id"] = str(uuid.uuid4())
    else: billing[0].pop("is_paid")
    before = (AuditEvent.objects.count(), CommandReceipt.objects.count())
    response = client.post(f"/api/v1/materials/{work['material']['id']}/issue-packages/",
        {"billing": billing, "reason": "ДЕМО · неверный первоначальный комплект"},
        content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 400
    assert not IssuePackage.objects.exists() and not PackageRevision.objects.exists()
    assert before == (AuditEvent.objects.count(), CommandReceipt.objects.count())


def test_each_work_has_independent_billing_and_new_work_is_unknown(employee_factory, grant):
    client, _, work, package, _, _, department, specialty, _ = prepare(employee_factory, grant, paid=True)
    response = register(client, work["receipt"], {"expected_version": 2, "registration_number": "152/3-1-26",
        "department_id": str(department.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False})
    assert response.status_code == 201
    second = response.json()
    package = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
    assert {item["id"]: item["is_paid"] for item in package["works"]} == {work["id"]: True, second["id"]: None}
    package = save_package(client, package, billing=[{"expertise_id": second["id"], "is_paid": False}]).json()["package"]
    assert {item["id"]: item["is_paid"] for item in package["works"]} == {work["id"]: True, second["id"]: False}


def test_paid_draft_replay_rechecks_current_prepare_right(employee_factory, grant):
    client, clerk, work, package, *_ = prepare(employee_factory, grant, paid=True)
    key = str(uuid.uuid4())
    values = {"billing": [{"expertise_id": work["id"], "is_paid": False}]}
    assert save_package(client, package, key=key, **values).status_code == 200
    clerk.role_assignments.filter(role__permissions__permission_code="issue.prepare").update(is_active=False)
    before = PackageRevision.objects.count()
    assert save_package(client, package, key=key, **values).status_code == 403
    assert PackageRevision.objects.count() == before


@pytest.mark.parametrize("category,kind", [("6", "expert_conclusion"), ("4", "research_act"), ("4", "sndz")])
def test_unsupported_result_category_pair_is_not_opened_by_a_paid_flag(employee_factory, grant, category, kind):
    # The result command already rejects mismatched category/kind. Deliberately
    # seed an inconsistent legacy pair to verify readiness also refuses it.
    valid_category = "6" if kind == "research_act" else "4"
    client, _, work, package, *_ = prepare(employee_factory, grant, category=valid_category, kind=kind, paid=True,
                                       kinds=["expert_subscription", "cover_letter", "invoice"])
    from apps.expertises.models import Expertise
    Expertise.objects.filter(pk=work["id"]).update(category_code=category)
    package = client.get(f"/api/v1/issue-packages/{package['id']}/").json()
    assert any(item["code"] == "policy_unconfirmed" for item in package["readiness"]["blockers"])
    assert package_command(client, package, "check").status_code == 400
