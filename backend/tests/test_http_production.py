import json
import uuid
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor,Request,build_opener
import pytest
from test_deadline_events import deadline_setup
from apps.personnel.models import Employee


def http_login(live_server,employee):
    browser=build_opener(HTTPCookieProcessor(CookieJar()));token=None
    def call(path,method="GET",body=None):
        headers={"Content-Type":"application/json","Idempotency-Key":str(uuid.uuid4())}
        if method!="GET":headers["X-CSRFToken"]=token
        request=Request(live_server.url+"/api/v1"+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        try:
            with browser.open(request,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as response:
            raw=response.read()
            return response.code,json.loads(raw) if response.headers.get("Content-Type","").startswith("application/json") else raw
    token=call("/auth/csrf/")[1]["csrf_token"]
    token=call("/auth/login/","POST",{"username":employee.user.username,"password":"Test-only-LongPassword9"})[1]["csrf_token"]
    return call


@pytest.mark.django_db(transaction=True)
def test_real_http_separate_sessions_suspend_request_agree_resume(live_server,employee_factory,grant):
    _,actor,work,clerk,_,_=deadline_setup(employee_factory,grant)
    clerk_employee=Employee.objects.get(user_id=clerk.session["_auth_user_id"])
    grant(clerk_employee,"expertise.deadline.record")
    expert_http=http_login(live_server,actor);clerk_http=http_login(live_server,clerk_employee)
    path=f"/expertises/{work['id']}"
    status,result=expert_http(path+"/suspend/","POST",{"expected_version":work["version"],"suspended_on":"2026-10-10","reason":"ДЕМО · ожидание материалов"})
    assert status==200
    work=result["expertise"]
    status,result=expert_http(path+"/deadline-events/","POST",{"expected_version":work["version"],"kind":"request","recorded_on":"2026-10-10","due_on":"2026-11-15","reason":"ДЕМО · запрос срока"})
    assert status==200 and result["expertise"]["production"]["current_due_on"] is None
    work=result["expertise"]
    status,evidence=clerk_http("/documents/","POST",{"kind":"deadline_agreement","title":"ДЕМО · согласование суда","source_kind":"paper_original"})
    assert status==201
    status,result=clerk_http(path+"/deadline-events/","POST",{"expected_version":work["version"],"kind":"agreement","recorded_on":"2026-10-11","due_on":"2026-11-15","reason":"ДЕМО · получен ответ","document_id":evidence["id"]})
    assert status==200
    work=result["expertise"]
    status,result=expert_http(path+"/resume/","POST",{"expected_version":work["version"],"resumed_on":"2026-10-11","reason":"ДЕМО · материалы поступили"})
    assert status==200 and result["expertise"]["state"]=="in_progress"
    reloaded=expert_http(path+"/")[1]
    assert reloaded["production"]["current_due_on"]=="2026-11-15"
    assert reloaded["production"]["initial_due_on"] is None
    assert reloaded["suspensions"][0]["resumed_on"]=="2026-10-11"
    assert reloaded["deadline_events"][1]["document"]["id"]==evidence["id"]
