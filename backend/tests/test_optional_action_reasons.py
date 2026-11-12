"""Action comments may be omitted without losing supplied audit explanations."""
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditEvent
from apps.correspondence.models import LetterAttachment
from apps.documents.models import Document
from apps.personnel.models import EmployeeOrgAssignment
from apps.references.models import Department, Position
from journal_samples import csv_source
from test_http_production import http_login
from test_journal_preview_api import preview_setup
from test_letter_commands import command_setup
from test_personnel_commands import client_for
from test_production import production_setup


REASONS = [({}, ""), ({"reason": ""}, ""), ({"reason": "   "}, ""),
           ({"reason": "Уточнение по исходному документу"}, "Уточнение по исходному документу")]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("comment,expected", REASONS)
def test_real_http_letter_creation_attachment_and_registration_keep_optional_comments(
        live_server, employee_factory, grant, comment, expected):
    _, actor, options, journals = command_setup(employee_factory, grant)
    http = http_login(live_server, actor)
    status, response = http("/letters/", "POST", {
        "direction": "incoming", "kind_id": options["kinds"][0]["id"],
        "subject": "Проверка документов", "sender_name": "Суд", **comment})
    assert status == 201, response
    letter = response["letter"]
    assert letter["content"]["reason"] == expected
    doc = Document.objects.create(kind="decision", title="Определение",
                                  source_kind="paper_original", created_by=actor)
    status, response = http(f"/letters/{letter['id']}/attachments/", "POST", {
        "expected_version": letter["version"], "document_id": str(doc.pk), **comment})
    assert status == 200, response
    letter = response["letter"]
    assert letter["attachments"][0]["reason"] == expected
    assert LetterAttachment.objects.get(letter_id=letter["id"]).reason == expected
    status, response = http(f"/letters/{letter['id']}/register/", "POST", {
        "expected_version": letter["version"], "journal_id": str(journals["incoming"].pk),
        "registration_number": "ВХ-1", "registered_on": "2026-10-02", **comment})
    assert status == 200, response
    assert response["letter"]["registration"]["reason"] == expected
    for action in ("letters.draft", "letters.attach", "letters.register"):
        assert AuditEvent.objects.get(action=action, object_id=letter["id"]).reason == expected


@pytest.mark.django_db
@pytest.mark.parametrize("comment,expected", REASONS)
def test_suspend_and_resume_default_comments_and_keep_audit_text(employee_factory, grant, comment, expected):
    client, _, work, *_ = production_setup(employee_factory, grant)
    for endpoint, date_field, on in (("suspend", "suspended_on", "2026-10-03"),
                                     ("resume", "resumed_on", "2026-10-04")):
        response = client.post(f"/api/v1/expertises/{work['id']}/{endpoint}/", {
            "expected_version": work["version"], date_field: on, **comment},
            content_type="application/json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        assert response.status_code == 200, response.content
        work = response.json()["expertise"]
        assert AuditEvent.objects.get(action=f"expertise.{endpoint}").reason == expected
    assert work["state"] == "in_progress"
    assert work["suspensions"][0]["reason"] == expected
    assert work["suspensions"][0]["resume_reason"] == expected


@pytest.mark.django_db
@pytest.mark.parametrize("comment,expected", REASONS)
def test_personnel_assignment_defaults_comment_and_audits_supplied_text(employee_factory, grant, comment, expected):
    actor = employee_factory()
    target = employee_factory()
    grant(actor, "employees.org_assignments.manage")
    department = Department.objects.create(code="3", name="Отдел 3")
    position = Position.objects.create(code="head", name="Начальник отдела")
    response = client_for(actor).post(f"/api/v1/employees/{target.pk}/org-assignments/", {
        "department_id": str(department.pk), "position_id": str(position.pk), **comment},
        content_type="application/json")
    assert response.status_code == 201, response.content
    assignment = EmployeeOrgAssignment.objects.get(pk=response.json()["id"])
    assert assignment.reason == expected
    assert AuditEvent.objects.get(action="employee.org_assignment.add", object_id=str(assignment.pk)).reason == expected


@pytest.mark.django_db
@pytest.mark.parametrize("comment,expected", REASONS)
def test_multipart_import_preview_defaults_comment_and_keeps_audit_text(
        employee_factory, grant, settings, tmp_path, comment, expected):
    settings.MEDIA_ROOT = tmp_path
    client, _ = preview_setup(employee_factory, grant)
    response = client.post("/api/v1/imports/preview/", {
        "file": SimpleUploadedFile("journal.csv", csv_source()), **comment},
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert response.status_code == 201, response.content
    assert AuditEvent.objects.get(action="imports.preview").reason == expected


@pytest.mark.django_db
@pytest.mark.parametrize("comment,expected", REASONS)
def test_report_plan_revision_defaults_comment_and_keeps_audit_text(employee_factory, grant, comment, expected):
    from test_report_plans import body, send, setup

    client, _ = setup(employee_factory, grant)
    payload = body(total=10)
    payload.pop("reason")
    response = send(client, {**payload, **comment})
    assert response.status_code == 200, response.content
    assert response.json()["revisions"][-1]["reason"] == expected
    assert AuditEvent.objects.get(action="reports.plan.save").reason == expected
