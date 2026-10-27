import pytest
from test_http_production import http_login
from test_letter_commands import command_setup, make_letter, registered, closure_reason


@pytest.mark.django_db(transaction=True)
def test_real_http_clerk_and_responsible_expert_finish_reply_control(live_server, employee_factory, grant):
    client, clerk, options, journals = command_setup(employee_factory, grant)
    expert = employee_factory()
    for action in ("letters.view", "letters.draft", "letters.reply", "control.view", "control.close"): grant(expert, action, "own")
    root = registered(client, make_letter(client, options), journals)
    clerk_http = http_login(live_server, clerk); expert_http = http_login(live_server, expert)
    def send(http, letter, endpoint, **body):
        return http(f"/letters/{letter['id']}/{endpoint}/", "POST", {"expected_version": letter["version"], "reason": "ДЕМО · межролевая проверка", **body})
    status, response = send(clerk_http, root, "assign", responsible_id=str(expert.pk))
    assert status == 200; root = response["letter"]
    status, response = send(clerk_http, root, "control", opened_on="2026-10-02", due_on=None)
    assert status == 200; root = response["letter"]
    status, response = expert_http("/letters/", "POST", {"direction": "outgoing", "parent_id": root["id"], "kind_id": options["kinds"][0]["id"], "subject": "Ответ суда", "reply_completeness": "final", "recipients": [{"name": "Суд"}], "reason": "ДЕМО · подготовка ответа"})
    assert status == 201; reply = response["letter"]
    assert send(expert_http, reply, "register", journal_id=str(journals["outgoing"].pk), registration_number="ИСХ-1", registered_on="2026-10-03")[0] == 403
    status, response = send(clerk_http, reply, "register", journal_id=str(journals["outgoing"].pk), registration_number="ИСХ-1", registered_on="2026-10-03")
    assert status == 200; reply = response["letter"]
    status, response = send(clerk_http, reply, "mark-sent", sent_on="2026-10-04", channel_id=options["channels"][0]["id"], recipient_ids=[r["id"] for r in reply["content"]["recipients"]])
    assert status == 200
    status, response = send(expert_http, root, "control/close", closed_on="2026-10-04", closure_reason_id=closure_reason(options, "reply_sent"), reply_id=reply["id"])
    assert status == 200 and response["letter"]["control"]["status"] == "closed"


@pytest.mark.django_db(transaction=True)
def test_real_http_outgoing_request_partial_additional_and_final_incoming_answers(live_server, employee_factory, grant):
    from test_letter_commands import command
    client, clerk, options, journals = command_setup(employee_factory, grant)
    expert = employee_factory()
    for action in ("letters.view", "letters.draft", "letters.reply", "control.view", "control.close"): grant(expert, action, "own")
    root = registered(client, make_letter(client, options, direction="outgoing"), journals)
    root = command(client, root, "control", opened_on="2026-10-02", due_on=None).json()["letter"]
    root = command(client, root, "assign", responsible_id=str(expert.pk)).json()["letter"]
    clerk_http = http_login(live_server, clerk); expert_http = http_login(live_server, expert)
    replies = []
    for index, completeness in enumerate(("partial", "additional", "final"), 1):
        status, response = expert_http("/letters/", "POST", {"direction": "incoming", "parent_id": root["id"], "kind_id": options["kinds"][0]["id"], "sender_name": "Суд", "subject": f"Часть ответа {index}", "reply_completeness": completeness, "received_on": "2026-10-03" if index < 3 else None, "reason": "ДЕМО · входящий ответ"})
        assert status == 201; reply = response["letter"]
        status, response = clerk_http(f"/letters/{reply['id']}/register/", "POST", {"expected_version": reply["version"], "journal_id": str(journals["incoming"].pk), "registration_number": f"ОТВ-{index}", "registered_on": "2026-10-03", "reason": "ДЕМО · регистрация"})
        assert status == 200; replies.append(response["letter"])
    path = f"/letters/{root['id']}/control/close/"
    body = {"expected_version": root["version"], "closed_on": "2026-10-05", "closure_reason_id": closure_reason(options, "reply_received"), "reply_id": replies[-1]["id"], "reason": "ДЕМО · проверка получения"}
    assert expert_http(path, "POST", body)[0] == 400
    status, response = clerk_http(f"/letters/{replies[-1]['id']}/mark-received/", "POST", {"expected_version": replies[-1]["version"], "received_on": "2026-10-05", "reason": "ДЕМО · получен окончательный ответ"})
    assert status == 200
    status, response = expert_http(path, "POST", body)
    assert status == 200 and response["letter"]["control"]["status"] == "closed"
