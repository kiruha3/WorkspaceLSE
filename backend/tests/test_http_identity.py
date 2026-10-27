import json
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener
import pytest


@pytest.mark.django_db(transaction=True)
def test_real_http_csrf_login_create_role_assign_and_read_back(live_server, employee_factory, grant):
    actor = employee_factory()
    target = employee_factory()
    grant(actor,"access.roles.manage")
    grant(actor,"access.roles.view")
    grant(actor,"access.roles.assign")
    cookies = CookieJar()
    browser = build_opener(HTTPCookieProcessor(cookies))
    token = None

    def call(path, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type":"application/json"}
        if method != "GET":
            headers["X-CSRFToken"] = token
        request = Request(live_server.url+"/api/v1"+path,data=data,headers=headers,method=method)
        with browser.open(request,timeout=5) as response:
            return response.status,json.load(response)

    _,csrf = call("/auth/csrf/")
    token = csrf["csrf_token"]
    _,login = call("/auth/login/","POST",{"username":actor.user.username,"password":"Test-only-LongPassword9"})
    token = login["csrf_token"]
    assert call("/me/")[1]["employee"]["id"] == str(actor.id)
    status,role = call("/roles/","POST",{"name":"HTTP проверка","permissions":[{"permission_code":"expertise.view","scope":"own"}]})
    assert status == 201
    status,assignment = call(f"/employees/{target.id}/roles/","POST",{"role_id":role["id"],"scope_limit":"own","department_ids":[],"reason":"Проверка полного HTTP-контракта"})
    assert status == 201
    assert call(f"/employees/{target.id}/roles/")[1][0]["id"] == assignment["id"]
    assert call(f"/roles/{role['id']}/")[1]["permissions"] == [{"permission_code":"expertise.view","scope":"own"}]
    assert call("/auth/logout/","POST",{})[1] == {"ok":True}
