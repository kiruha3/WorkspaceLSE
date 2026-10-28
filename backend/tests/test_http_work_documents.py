import pytest
from test_http_production import http_login
from test_work_document_vault import vault


@pytest.mark.django_db(transaction=True)
def test_real_session_reads_archive_capability_and_basis(live_server, vault):
    _, owner, (work, _), basis = vault
    http = http_login(live_server, owner)
    status, data = http('/me/')
    assert status == 200 and 'work_documents' in data['supported_modules']
    status, data = http(f'/expertises/{work.pk}/documents/')
    assert status == 200, data
    assert data['results'][0]['document']['id'] == str(basis.pk)


@pytest.mark.django_db(transaction=True)
def test_real_session_creates_reference_links_two_works_and_detaches_only_one(live_server,vault):
    _,owner,(one,two),_=vault
    http=http_login(live_server,owner)
    status,doc=http('/documents/','POST',{'kind':'case_material','title':'ДЕМО · общая внешняя ссылка',
        'source_kind':'external_link','source_url':'https://example.org/case.pdf'})
    assert status==201,doc
    path=f'/expertises/{one.pk}/documents/'
    status,linked=http(path,'POST',{'expected_version':1,'document_id':doc['id'],'note':'Общее приложение','reason':'Дослано'})
    assert status==200,linked
    row=next(item for item in linked['library']['results'] if item['document']['id']==doc['id'])
    assert row['document']['versions']==[] and row['document']['source_kind']=='external_link'
    status,second=http(f'/expertises/{two.pk}/documents/','POST',{'expected_version':1,'document_id':doc['id'],'reason':'Та же ссылка'})
    assert status==200,second
    status,removed=http(path+row['extra_links'][0]['id']+'/detach/','POST',{'expected_version':2,'reason':'Снять только здесь'})
    assert status==200,removed
    status,other=http(f'/expertises/{two.pk}/documents/')
    assert status==200 and doc['id'] in [item['document']['id'] for item in other['results']]


@pytest.mark.django_db(transaction=True)
def test_creating_external_reference_does_not_contact_its_http_server(live_server,vault):
    from http.server import BaseHTTPRequestHandler,HTTPServer
    from threading import Thread
    requested=[]
    class Source(BaseHTTPRequestHandler):
        def do_GET(self):
            requested.append(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'%PDF-1.0')
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Source)
    worker=Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        _,owner,_,_=vault
        http=http_login(live_server,owner)
        status,doc=http('/documents/','POST',{'kind':'case_material','title':'Ссылка без скачивания','source_kind':'external_link',
            'source_url':f'http://127.0.0.1:{server.server_port}/source.pdf'})
        assert status==201,doc
        assert doc['versions']==[] and requested==[]
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)
