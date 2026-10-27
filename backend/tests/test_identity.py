from django.test import Client


def test_anonymous_identity_has_json_auth_required_not_a_login_redirect():
    response = Client().get("/api/v1/me/")
    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"


def test_login_requires_csrf_before_creating_a_session(db):
    response = Client(enforce_csrf_checks=True).post(
        "/api/v1/auth/login/", {"username": "missing", "password": "missing"},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_real_session_login_identity_and_logout(employee_factory):
    employee = employee_factory()
    client = Client(enforce_csrf_checks=True)
    token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
    response = client.post("/api/v1/auth/login/", {"username":employee.user.username,"password":"Test-only-LongPassword9"}, content_type="application/json",HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 200
    response = client.get("/api/v1/me/")
    assert response.status_code == 200
    assert response.json()["employee"]["id"] == str(employee.id)
    token = client.cookies["csrftoken"].value
    assert client.post("/api/v1/auth/logout/",HTTP_X_CSRFTOKEN=token).status_code == 200
    assert client.get("/api/v1/me/").status_code == 401


def test_disabling_account_ends_access_for_existing_session(employee_factory):
    employee = employee_factory()
    client = Client()
    client.force_login(employee.user)
    assert client.get("/api/v1/me/").status_code == 200
    employee.user.is_active = False
    employee.user.save()
    assert client.get("/api/v1/me/").status_code == 401
