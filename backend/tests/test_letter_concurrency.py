from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid
import pytest
from django.db import close_old_connections, connection
from django.test import Client
from test_letter_commands import command_setup, make_letter, command, registered, closure_reason

pytestmark = pytest.mark.django_db(transaction=True)


def parallel(actor, operations):
    barrier = Barrier(len(operations))
    def run(operation):
        close_old_connections()
        try:
            client = Client(); client.force_login(actor.user); barrier.wait(timeout=10)
            with connection.cursor() as cursor: cursor.execute("SET lock_timeout = '5s'")
            response = operation(client)
            return response.status_code, response.json()
        finally: connection.close()
    with ThreadPoolExecutor(max_workers=len(operations)) as pool: return list(pool.map(run, operations))


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_registration_same_letter_has_one_fact(employee_factory, grant, same_key):
    client, actor, options, journals = command_setup(employee_factory, grant)
    letter = make_letter(client, options); keys = [str(uuid.uuid4()), str(uuid.uuid4())]
    if same_key: keys[1] = keys[0]
    values = {"journal_id": str(journals["incoming"].pk), "registration_number": "ВХ-1", "registered_on": "2026-10-02"}
    responses = parallel(actor, [lambda c, key=key: command(c, letter, "register", key=key, **values) for key in keys])
    assert sorted(r[0] for r in responses) == ([200, 200] if same_key else [200, 409])
    from apps.correspondence.models import LetterRegistration
    assert LetterRegistration.objects.count() == 1
    if same_key: assert responses[0][1]["event"] == responses[1][1]["event"]


def test_concurrent_numbers_on_distinct_letters_conflict_without_partial_registration(employee_factory, grant):
    client, actor, options, journals = command_setup(employee_factory, grant)
    letters = [make_letter(client, options), make_letter(client, options)]
    responses = parallel(actor, [lambda c, letter=letter: command(c, letter, "register", journal_id=str(journals["incoming"].pk), registration_number="ВХ-1", registered_on="2026-10-02") for letter in letters])
    assert sorted(r[0] for r in responses) == [200, 409]
    from apps.correspondence.models import LetterRegistration
    assert LetterRegistration.objects.count() == 1


def test_close_racing_reply_send_observes_a_complete_fact_without_deadlock(employee_factory, grant):
    client, actor, options, journals = command_setup(employee_factory, grant)
    root = registered(client, make_letter(client, options), journals)
    root = command(client, root, "control", opened_on="2026-10-02", due_on=None).json()["letter"]
    reply = registered(client, make_letter(client, options, direction="outgoing", parent=root, completeness="final"), journals, number="ИСХ-1")
    responses = parallel(actor, [
        lambda c: command(c, root, "control/close", closed_on="2026-10-04", closure_reason_id=closure_reason(options, "reply_sent"), reply_id=reply["id"]),
        lambda c: command(c, reply, "mark-sent", sent_on="2026-10-04", channel_id=options["channels"][0]["id"], recipient_ids=[r["id"] for r in reply["content"]["recipients"]]),
    ])
    assert responses[1][0] == 200 and responses[0][0] in (200, 400)
    current = client.get(f"/api/v1/letters/{root['id']}/").json()
    if current["control"]["status"] == "closed":
        assert client.get(f"/api/v1/letters/{reply['id']}/").json()["state"] == "sent"
