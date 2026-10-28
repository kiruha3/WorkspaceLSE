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
    from apps.references.models import Department, Position, Specialty, LetterJournal
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
    for direction in ('incoming','outgoing'):
        LetterJournal.objects.get_or_create(code='accept_'+direction, defaults={'name':'ПРИЁМКА · '+direction, 'direction':direction})
    return {'profiles':profiles, 'department':{'id':str(dept.pk),'code':'3'}, 'specialty':{'id':str(spec.pk),'code':'1.1'}}
