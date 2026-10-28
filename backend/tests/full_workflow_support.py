"""Synthetic identity fixtures shared by HTTP tests and the isolated UI runtime."""
def create_people(password: str) -> dict:
    from django.db import connection
    name = connection.settings_dict['NAME']
    if not (name.startswith('test_') or name.startswith('ais_lse_acceptance_')):
        raise ValueError('Synthetic identities are allowed only in isolated acceptance/test databases')
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from apps.accounts.models import Role, RolePermission
    from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeRole, EmployeeSpecialty
    from apps.references.models import Department, Position, Specialty, LetterJournal, AuthorityType
    from apps.references.authority_seeds import AUTHORITY_TYPES
    from apps.accounts.catalog import PERMISSIONS

    dept, _ = Department.objects.get_or_create(code='3', defaults={'name': 'ПРИЁМКА · отдел 3'})
    Department.objects.get_or_create(code='4', defaults={'name': 'ПРИЁМКА · отдел 4'})
    spec, _ = Specialty.objects.get_or_create(code='1.1', defaults={'name': 'Почерковедческая'})
    Specialty.objects.get_or_create(code='13.1', defaults={'name': 'ПРИЁМКА · обучение другой специальности'})
    expert_actions = ('expertise.view','expertise.work.update','expertise.suspend','expertise.resume','expertise.deadline.record',
        'expertise.result.draft','expertise.complete','documents.view','documents.upload','letters.view','letters.draft',
        'letters.reply','letters.attach','control.view','control.close','issue.view')
    roles = {
        'clerk': {code:'institution' for code in ('receipts.view','receipts.create','receipts.accept','receipts.amend',
            'expertise.view','expertise.register','expertise.work.update','documents.view','documents.upload','documents.link','documents.unlink',
            'letters.view','letters.draft','letters.reply','letters.attach','letters.register','letters.mark_sent',
            'letters.mark_received','letters.mark_delivered','control.view','control.assign','control.close','control.reopen',
            'issue.view','issue.prepare','issue.check','issue.confirm','references.view')},
        'head': {**{code:'own' for code in expert_actions}, **{code:'departments' for code in ('expertise.view','expertise.assign','expertise.reassign','employees.view')}},
        'expert': {code:'own' for code in expert_actions},
        'expert2': {code:'own' for code in expert_actions},
        'trainee': {'expertise.view':'own','documents.view':'own'},
        'hr': {code:'institution' for code in ('employees.view','employees.create','employees.update','employees.org_assignments.manage','specialties.training.manage','specialties.qualify','references.view')},
        'access': {code:'institution' for code in ('access.roles.view','access.roles.manage','access.roles.assign','access.effective.view','users.view','users.create','users.deactivate','references.view')},
        'director': {code:'institution' for code in ('expertise.view','documents.view','letters.view','control.view','issue.view','reports.form151.run','reports.form151.download')},
    }
    labels = {'clerk':'Делопроизводитель','head':'Начальник и эксперт','expert':'Эксперт','expert2':'Эксперт-получатель',
        'trainee':'Стажёр','hr':'Кадровик','access':'Администратор доступа','director':'Директор'}
    profiles = {}
    for code, permissions in roles.items():
        user = get_user_model().objects.create_user(username='accept.'+code, password=password)
        employee = Employee.objects.create(user=user, full_name='ПРИЁМКА · '+labels[code])
        position, _ = Position.objects.get_or_create(code='accept_'+code, defaults={'name': labels[code]})
        EmployeeOrgAssignment.objects.create(employee=employee, department=dept, position=position)
        role = Role.objects.create(name='ПРИЁМКА · '+labels[code])
        for action, scope in permissions.items():
            assert scope in PERMISSIONS[action].scopes, (action, scope)
            RolePermission.objects.create(role=role, permission_code=action, scope=scope)
        assigned = EmployeeRole.objects.create(employee=employee, role=role, scope_limit='institution')
        assigned.departments.add(dept)
        if code in ('head','expert','expert2','trainee'):
            EmployeeSpecialty.objects.create(employee=employee, specialty=spec, status='training' if code=='trainee' else 'qualified')
        profiles[code] = {'username':user.username, 'employee_id':str(employee.pk)}
    for command in ('seed_result_catalogs','seed_correspondence_catalogs','seed_issue_catalogs'):
        call_command(command, verbosity=0)
    for code,name,group in AUTHORITY_TYPES:
        AuthorityType.objects.get_or_create(code=code,defaults={'name':name,'report_group':group})
    for direction in ('incoming','outgoing'):
        LetterJournal.objects.get_or_create(code='accept_'+direction, defaults={'name':'ПРИЁМКА · '+direction, 'direction':direction})
    return {'profiles':profiles, 'department':{'id':str(dept.pk),'code':'3'}, 'specialty':{'id':str(spec.pk),'code':'1.1'}}


class WorkflowSession:
    """Actual independent HTTP session; never calls Django commands/models for facts."""
    def __init__(self, base, username, password):
        from http.cookiejar import CookieJar
        from urllib.request import build_opener, HTTPCookieProcessor
        self.base=base.rstrip('/');self.csrf=None
        self.browser=build_opener(HTTPCookieProcessor(CookieJar()))
        self.csrf=self.ok('/auth/csrf/')['csrf_token']
        self.csrf=self.ok('/auth/login/','POST',{'username':username,'password':password})['csrf_token']

    def request(self,path,method='GET',body=None,key=None,files=None):
        import json,uuid
        from urllib.request import Request
        from urllib.error import HTTPError
        if not path.startswith('/') or path.startswith('//'):raise ValueError('Only same-origin API paths')
        url=self.base+(path if path.startswith('/api/v1/') else '/api/v1'+path)
        headers={'Accept':'application/json, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        data=None
        if method!='GET':
            headers.update({'X-CSRFToken':self.csrf,'Idempotency-Key':key or str(uuid.uuid4()),'Origin':self.base,'Referer':self.base+'/'})
        if files:
            boundary='acceptance-'+uuid.uuid4().hex;parts=[]
            for name,value in (body or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            for name,(filename,raw,kind) in files.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {kind}\r\n\r\n'.encode()+raw+b'\r\n')
            data=b''.join(parts)+f'--{boundary}--\r\n'.encode();headers['Content-Type']='multipart/form-data; boundary='+boundary
        elif body is not None:
            data=json.dumps(body,ensure_ascii=False).encode();headers['Content-Type']='application/json'
        request=Request(url,data=data,headers=headers,method=method)
        try:response=self.browser.open(request,timeout=20)
        except HTTPError as error:response=error
        with response:
            raw=response.read()
            value=json.loads(raw) if response.headers.get('Content-Type','').startswith('application/json') else raw
            return response.status,value

    def ok(self,path,method='GET',body=None,*,status=200,key=None,files=None):
        actual,value=self.request(path,method,body,key,files)
        assert actual==status,(path,actual,value)
        return value


def sample_png():
    import base64
    return base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII=')


def document(http,kind,title,*,department=None,upload=False):
    value=http.ok('/documents/','POST',{'kind':kind,'title':title,'source_kind':'uploaded_copy' if upload else 'paper_original','department_id':department},status=201)
    if upload:upload_copy(http,value)
    return http.ok(f"/documents/{value['id']}/")


def upload_copy(http,doc,*,filename='acceptance.png',raw=None):
    return http.ok(f"/documents/{doc['id']}/versions/",'POST',{'expected_version':doc['version'],'relative_path':'Материал/'+filename},
        status=201,files={'file':(filename,sample_png() if raw is None else raw,'image/png')})


def register_work(clerk,world,*,number='1/3-1-26',is_demo=False):
    basis=document(clerk,'resolution','ПРИЁМКА · синтетическое постановление, не документ суда',department=world['department']['id'])
    receipt=clerk.ok('/receipts/','POST',{'received_at':'2026-10-01','sender_name':'ПРИЁМКА · условный орган',
        'material_title':'ПРИЁМКА · только изолированные контрольные материалы','is_demo':is_demo,
        'department_id':world['department']['id'],'basis_document_id':basis['id']},status=201)
    receipt=clerk.ok(f"/receipts/{receipt['id']}/register/",'POST',{'expected_version':receipt['version']})
    work=clerk.ok(f"/receipts/{receipt['id']}/expertises/",'POST',{'expected_version':receipt['version'],
        'registration_number':number,'department_id':world['department']['id'],'specialty_id':world['specialty']['id'],
        'appointment_nature':'primary','is_commission':False},status=201)
    assert work['current_assignments']==[] and work['basis_document']['versions']==[]
    return work


def work_command(http,work,endpoint,**body):
    return http.ok(f"/expertises/{work['id']}/{endpoint}/",'POST',{'expected_version':work['version'],'reason':'ПРИЁМКА · подтверждённый учебный факт',**body})['expertise']


def complete_simple_work(expert,work):
    doc=document(expert,'expert_conclusion','ПРИЁМКА · синтетический результат начальника',upload=True)
    work=work_command(expert,work,'result',kind='expert_conclusion',completed_on='2026-10-10',document_id=doc['id'],
        complexity_level=1,questions=1,categorical=1,probable=0,unresolved=0,statistics_complete=True,allocations_complete=True)
    return work_command(expert,work,'complete',result_id=work['result']['id'])


def run_journey(base,people,password):
    import uuid
    profiles=people['profiles']
    sessions={code:WorkflowSession(base,value['username'],password) for code,value in profiles.items()}
    clerk,head,expert,director=(sessions[name] for name in ('clerk','head','expert','director'))
    work=register_work(clerk,people);path=f"/expertises/{work['id']}"
    invalid={'expected_version':work['version'],'employee_ids':[profiles['trainee']['employee_id']],'reason':'ПРИЁМКА · проверить отказ обучаемому'}
    assert head.request(path+'/assignments/','POST',invalid)[0]==400
    invalid['employee_ids']=[profiles['expert']['employee_id']]
    assert director.request(path+'/assignments/','POST',invalid)[0]==403
    work=head.ok(path+'/assignments/','POST',invalid)
    assert sessions['hr'].request(path+'/')[0]==403 and sessions['access'].request(path+'/')[0]==403
    assert expert.request(path+'/assignments/','POST',invalid)[0]==403
    assert sessions['trainee'].ok('/expertises/')['count']==0
    assert sessions['hr'].ok('/employees/')['count']==8
    assert len(sessions['access'].ok('/permissions/'))>0

    # Receipt basis is a mutable source association, unlike an explicitly pinned closure/check file.
    basis=clerk.ok(f"/documents/{work['basis_document']['id']}/")
    scan=upload_copy(clerk,basis,filename='basis.png')
    assert clerk.ok(scan['download_url'])==sample_png()
    archive=clerk.ok(path+'/documents/')
    origin=next(row for row in archive['results'] if row['document']['id']==basis['id'])
    assert origin['origins'][0]['kind']=='receipt_basis' and 'accepted_version_id' not in origin['origins'][0]
    assert origin['document']['versions'][0]['id']==scan['id']
    options=expert.ok(path+'/case-details/')
    authority=next(row['id'] for row in options['authority_types'] if row['code']=='mvd')
    work=work_command(expert,work,'case-details',authority_type_id=authority,authority_name='ПРИЁМКА · условный отдел МВД',
        official='ПРИЁМКА · должностное лицо',contact='',case_number='ACCEPT-1',case_description='Синтетическое дело',
        basis_text='Учебное постановление',inventory='Один условный том, копии документов',questions_text='Четыре контрольных вопроса',
        decree3214=False,decree_document_id=None,decree_basis='')
    work=work_command(expert,work,'deadline-events',kind='initial',recorded_on='2026-10-02',due_on='2026-10-12')
    work=work_command(expert,work,'suspend',suspended_on='2026-10-03')
    request_doc=document(expert,'deadline_request','ПРИЁМКА · ходатайство о материалах и продлении',upload=True)
    work=work_command(expert,work,'deadline-events',kind='request',recorded_on='2026-10-03',due_on='2026-10-20',document_id=request_doc['id'])
    assert work['production']['current_due_on']=='2026-10-12'
    agreement=document(expert,'deadline_agreement','ПРИЁМКА · бумажное согласование срока')
    work=work_command(expert,work,'deadline-events',kind='agreement',recorded_on='2026-10-04',due_on='2026-10-20',document_id=agreement['id'])
    work=work_command(expert,work,'resume',resumed_on='2026-10-05')
    assert work['production']['current_due_on']=='2026-10-20' and work['state']=='in_progress'

    letter_options=clerk.ok('/letters/options/')
    kind=lambda code:next(row['id'] for row in letter_options['kinds'] if row['code']==code)
    journal=lambda direction:next(row['id'] for row in letter_options['journals'] if row['direction']==direction)
    def letter_command(http,letter,endpoint,**body):
        return http.ok(f"/letters/{letter['id']}/{endpoint}/",'POST',{'expected_version':letter['version'],'reason':'ПРИЁМКА · факт переписки',**body})['letter']
    root=expert.ok('/letters/','POST',{'direction':'outgoing','kind_id':kind('request'),'subject':'ПРИЁМКА · ходатайство о материалах и продлении',
        'document_on':'2026-10-03','sender_name':'ПРИЁМКА · лаборатория','department_id':people['department']['id'],
        'expertise_ids':[work['id']],'material_id':work['material']['id'],'recipients':[{'name':'ПРИЁМКА · условный орган'}],
        'reason':'ПРИЁМКА · проект ходатайства'},status=201)['letter']
    root=letter_command(expert,root,'attachments',document_id=request_doc['id'])
    root=letter_command(clerk,root,'register',journal_id=journal('outgoing'),registration_number='ПРИЁМКА-ИСХ-1',registered_on='2026-10-03')
    root=letter_command(clerk,root,'mark-sent',sent_on='2026-10-03',channel_id=letter_options['channels'][0]['id'],recipient_ids=[r['id'] for r in root['content']['recipients']])
    root=letter_command(clerk,root,'control',opened_on='2026-10-03',due_on='2026-10-07',due_basis='ПРИЁМКА · срок ответа из запроса')
    replies=[]
    for index,completeness in enumerate(('partial','final'),1):
        reply=expert.ok('/letters/','POST',{'direction':'incoming','parent_id':root['id'],'kind_id':kind('reply'),
            'subject':'ПРИЁМКА · '+completeness+' ответ','sender_name':'ПРИЁМКА · условный орган',
            'reply_completeness':completeness,'received_on':'2026-10-05','document_on':'2026-10-05',
            'expertise_ids':[work['id']],'material_id':work['material']['id'],'reason':'ПРИЁМКА · поступил ответ'},status=201)['letter']
        reply=letter_command(clerk,reply,'register',journal_id=journal('incoming'),registration_number=f'ПРИЁМКА-ВХ-{index}',registered_on='2026-10-05')
        replies.append(reply)
        root=expert.ok(f"/letters/{root['id']}/")
        assert root['control']['status']=='open'

    work=work_command(expert,work,'timing',reasons_complete=True,primary_reason_id=None,reasons=[],notification_sent=False,
        notification_on=None,notification_document_id=None,extension_requested=True,request_on='2026-10-03',request_document_id=request_doc['id'],
        deadline_breached=False,breach_basis='ПРИЁМКА · окончание10октября до согласованного20октября',breach_document_id=agreement['id'])
    result_doc=document(expert,'expert_conclusion','ПРИЁМКА · результат, не судебное заключение',upload=True)
    reason=next(row['id'] for row in expert.ok(path+'/result-options/')['unresolved_reasons'] if row['code']=='materials_insufficient')
    work=work_command(expert,work,'result',kind='expert_conclusion',completed_on='2026-10-10',document_id=result_doc['id'],
        complexity_level=2,questions=4,categorical=2,probable=1,unresolved=1,statistics_complete=True,
        unresolved_allocations=[{'reason_id':reason,'count':1,'comment':'ПРИЁМКА · один нерешённый вопрос','document_id':None}],allocations_complete=True)
    work=work_command(expert,work,'complete',result_id=work['result']['id'])
    accepted=work['closure']['document']['accepted_version_id']
    root=expert.ok(f"/letters/{root['id']}/");assert root['control']['status']=='open'
    close_reason=next(row['id'] for row in letter_options['closure_reasons'] if row['rule']=='reply_received')
    root=letter_command(expert,root,'control/close',closed_on='2026-10-10',closure_reason_id=close_reason,reply_id=replies[-1]['id'])
    assert root['control']['status']=='closed'
    late=upload_copy(expert,expert.ok(f"/documents/{result_doc['id']}/"),filename='later-result.png',raw=sample_png()+b'late-copy')
    assert expert.ok(path+'/')['closure']['document']['accepted_version_id']==accepted

    items=[]
    for item_kind in ('expert_subscription','cover_letter','notification'):
        doc=document(clerk,item_kind,'ПРИЁМКА · '+item_kind)
        items.append({'kind':item_kind,'expertise_id':work['id'],'document_id':doc['id'],'note':''})
    package=clerk.ok(f"/materials/{work['material']['id']}/issue-packages/",'POST',{
        'materials_description':'ПРИЁМКА · материалы дела, подписка, результат, сопроводительное и уведомление',
        'items':items,'billing':[{'expertise_id':work['id'],'is_paid':True}],'reason':'ПРИЁМКА · платная работа'},status=201)['package']
    pack_path=f"/issue-packages/{package['id']}"
    assert any(row.get('field')=='invoice' and row['code']=='item_missing' for row in package['readiness']['blockers'])
    assert clerk.request(pack_path+'/check/','POST',{'expected_version':package['version'],'reason':'ПРИЁМКА · нет счёта'})[0]==400
    invoice=document(clerk,'invoice','ПРИЁМКА · счёт, не документ для оплаты',upload=True)
    items.append({'kind':'invoice','expertise_id':work['id'],'document_id':invoice['id'],'note':''})
    package=clerk.ok(pack_path+'/draft/','POST',{'expected_version':package['version'],'materials_description':'ПРИЁМКА · полный комплект и один том',
        'items':items,'billing':[{'expertise_id':work['id'],'is_paid':True}],'reason':'ПРИЁМКА · счёт подкреплён'})['package']
    package=clerk.ok(pack_path+'/check/','POST',{'expected_version':package['version'],'reason':'ПРИЁМКА · комплект сверен'})['package']
    assert package['readiness']['can_issue']
    methods=clerk.ok('/issue-packages/options/')['methods']
    body={'expected_version':package['version'],'reason':'ПРИЁМКА · фактическая учебная передача','issued_on':'2026-10-14',
        'method_id':next(row['id'] for row in methods if row['code']=='in_person'),'recipient_name':'ПРИЁМКА · условный получатель',
        'recipient_basis':'ПРИЁМКА · условная доверенность','tracking':'','comment':'','evidence_document_id':None}
    assert expert.request(pack_path+'/issue/','POST',body)[0]==403
    key=str(uuid.uuid4())
    issued=clerk.ok(pack_path+'/issue/','POST',body,key=key)
    replay=clerk.ok(pack_path+'/issue/','POST',body,key=key)
    assert replay['event']==issued['event'] and issued['package']['state']=='issued'
    assert issued['package']['issuance']['issued_on']=='2026-10-14'
    assert expert.ok(path+'/issue-status/')['status']=='issued'
    report=director.ok('/reports/form151/?source=registry&year=2026&month=10&opening_balances_complete=true')
    cells={(row['sheet'],row['address']):row for row in report['cells']}
    for section,address,want in ((1,'E108',1),(1,'J108',1),(1,'K108',1),(1,'Q108',0),
            (2,'D107',4),(2,'E107',3),(2,'F107',2),(2,'G107',1),(2,'H107',1),
            (3,'D107',1),(4,'E107',1),(5,'G108',1),(6,'E107',1),(6,'G107',1),(6,'H107',1)):
        assert cells[f'Раздел {section}',address]['value']==want,(section,address,cells[f'Раздел {section}',address])
    assert work['id'] in cells['Раздел 1','J108']['rows']
    assert report['source']['row_count']==1 and report['records'][work['id']]['registration_number']=='1/3-1-26'
    xlsx=director.ok(report['download_url'])
    return {'work_id':work['id'],'receipt_id':work['receipt']['id'],'material_id':work['material']['id'],
        'package_id':package['id'],'letter_id':root['id'],'reply_ids':[row['id'] for row in replies],
        'accepted_result_file':accepted,'late_result_file':late['id'],'issued_on':'2026-10-14','xlsx':xlsx,
        'report_revision':report['data_revision']}
