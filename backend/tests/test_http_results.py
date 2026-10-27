import pytest
from test_http_production import http_login
from test_result_completion import completion_setup,ready_result,result_body


@pytest.mark.django_db(transaction=True)
def test_real_http_separate_sessions_draft_complete_read_and_correct(live_server,employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor,work,_,head,_,_=completion_setup(employee_factory,grant)
    grant(head,"expertise.closed.correct")
    work=ready_result(client,work)
    expert_http=http_login(live_server,actor);head_http=http_login(live_server,head)
    path=f"/expertises/{work['id']}"
    status,response=expert_http(path+"/result/","POST",{"expected_version":work["version"],"reason":"ДЕМО · документ проверен",**result_body(work,questions=1,categorical=1,probable=0,unresolved=0,statistics_complete=True)})
    assert status==200;work=response["expertise"]
    status,response=expert_http(path+"/complete/","POST",{"expected_version":work["version"],"reason":"ДЕМО · окончено","result_id":work["result"]["id"]})
    assert status==200;work=response["expertise"]
    assert head_http(path+"/")[1]["closure"]["id"]==work["closure"]["id"]
    status,response=head_http(path+"/correct/","POST",{"expected_version":work["version"],"reason":"ДЕМО · уточнена сложность","correction_kind":"result","result":result_body(work,complexity_level=2)})
    assert status==200 and response["expertise"]["result"]["complexity_level"]==2
    assert expert_http(path+"/")[1]["result"]["complexity_level"]==2
