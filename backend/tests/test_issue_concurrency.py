import uuid
import pytest
from apps.issuance.models import MaterialIssue
from apps.expertises.models import Expertise, WorkClosure
from test_issue_commands import ready_package, checked, package_command, issue_values
from test_letter_concurrency import parallel
from test_registration import register
from test_result_completion import send, result_body
from test_basis_documents import upload

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("same_key", [True, False])
def test_two_issue_commands_have_one_fact(employee_factory, grant, settings, tmp_path, same_key):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, _, package, _, _, _, _ = ready_package(employee_factory, grant)
    package = checked(client, package)
    keys = [str(uuid.uuid4()), str(uuid.uuid4())]
    if same_key: keys[1] = keys[0]
    responses = parallel(clerk, [lambda session, key=key: package_command(session, package, "issue", key=key, **issue_values()) for key in keys])
    assert sorted(result[0] for result in responses) == ([200, 200] if same_key else [200, 409])
    assert MaterialIssue.objects.count() == 1
    if same_key: assert responses[0][1]["event"] == responses[1][1]["event"]


def test_issue_and_new_registration_cannot_both_commit(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, work, package, _, _, department, specialty = ready_package(employee_factory, grant)
    package = checked(client, package)
    values = {"expected_version": 2, "registration_number": "152/3-1-26", "department_id": str(department.pk), "specialty_id": str(specialty.pk), "appointment_nature": "primary", "is_commission": False}
    responses = parallel(clerk, [
        lambda session: package_command(session, package, "issue", **issue_values()),
        lambda session: register(session, work["receipt"], values),
    ])
    assert tuple(result[0] for result in responses) in ((200, 400), (400, 201))
    if MaterialIssue.objects.exists(): assert Expertise.objects.filter(material_id=work["material"]["id"]).count() == 1
    else: assert Expertise.objects.filter(material_id=work["material"]["id"]).count() == 2


def test_issue_and_closed_correction_cannot_create_stale_issued_result(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, work, package, _, _, _, _ = ready_package(employee_factory, grant)
    grant(clerk, "expertise.closed.correct")
    package = checked(client, package)
    responses = parallel(clerk, [
        lambda session: package_command(session, package, "issue", **issue_values()),
        lambda session: send(session, work, "correct", correction_kind="result", result=result_body(work, note="Сверена редакция")),
    ])
    assert tuple(result[0] for result in responses) in ((200, 400), (400, 200))
    assert WorkClosure.objects.filter(expertise_id=work["id"]).count() == (1 if MaterialIssue.objects.exists() else 2)


def test_supplement_upload_race_keeps_checked_bytes_or_requires_recheck(employee_factory, grant, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    client, clerk, _, package, _, _, _, _ = ready_package(employee_factory, grant, uploaded=True)
    package = checked(client, package)
    item = package["content"]["items"][0]
    checked_version = next(file["document"]["accepted_version_id"] for file in package["checks"][0]["files"] if file["item_id"] == item["id"])
    responses = parallel(clerk, [
        lambda session: package_command(session, package, "issue", **issue_values()),
        lambda session: upload(session, item["document"]["id"], version=2),
    ])
    assert responses[1][0] == 201 and responses[0][0] in (200, 400)
    if responses[0][0] == 200:
        issued = responses[0][1]["package"]
        version = next(file["document"]["accepted_version_id"] for file in issued["checks"][0]["files"] if file["item_id"] == item["id"])
        assert version == checked_version
