import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import User, Role, RolePermission
from apps.accounts.management.commands.bootstrap_access import stable_id, TEMPLATES, CORRESPONDENCE_NEW_RIGHTS, ISSUANCE_NEW_RIGHTS, IMPORT_PREVIEW_NEW_RIGHTS
from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeRole, EmployeeSpecialty
from apps.references.models import Department, Position, Specialty


class Command(BaseCommand):
    help="Явные учебные профили. Не назначает роли реальным сотрудникам, не создаёт записей журнала и не сбрасывает существующие пароли."

    def add_arguments(self,parser):
        parser.add_argument("--enable-results",action="store_true",help="Явно добавить два новых права результата только учебной роли эксперта")
        parser.add_argument("--enable-correspondence",action="store_true",help="Явно добавить новые права переписки только учебным ролям эксперта и делопроизводителя")
        parser.add_argument("--enable-issuance",action="store_true",help="Явно добавить новые права выдачи только учебным ролям эксперта и делопроизводителя")
        parser.add_argument("--enable-import-preview",action="store_true",help="Явно добавить права предпросмотра переноса только учебному делопроизводителю")

    @transaction.atomic
    def handle(self,*args,**options):
        department,_=Department.objects.get_or_create(code="3",defaults={"name":"Отдел 3"})
        specialty,_=Specialty.objects.get_or_create(code="1.1",defaults={"name":"Исследование почерка и подписей"})
        profiles=[("clerk","Делопроизводитель","clerk"),("head3","Руководитель отдела","head"),("expert","Эксперт","expert"),("expert2","Эксперт","expert"),("trainee","Эксперт","expert")]
        if options["enable_import_preview"]:
            role=Role.objects.filter(pk=stable_id("workflow-demo:role:Делопроизводитель")).first()
            if role and role.assignments.exclude(employee_id=stable_id("workflow-demo:employee:demo.clerk")).exists():
                raise CommandError("В учебной роли есть неучебный сотрудник: расширение переноса запрещено.")
        if options["enable_issuance"]:
            for template, logins in (("Эксперт", ("expert","expert2","trainee")), ("Делопроизводитель", ("clerk",))):
                role=Role.objects.filter(pk=stable_id("workflow-demo:role:"+template)).first()
                allowed=[stable_id("workflow-demo:employee:demo."+login) for login in logins]
                if role and role.assignments.exclude(employee_id__in=allowed).exists():
                    raise CommandError("В учебной роли есть неучебный сотрудник: расширение выдачи запрещено.")
        if options["enable_correspondence"]:
            for template, logins in (("Эксперт", ("expert","expert2","trainee")), ("Делопроизводитель", ("clerk",))):
                role=Role.objects.filter(pk=stable_id("workflow-demo:role:"+template)).first()
                allowed=[stable_id("workflow-demo:employee:demo."+login) for login in logins]
                if role and role.assignments.exclude(employee_id__in=allowed).exists():
                    raise CommandError("В учебной роли есть неучебный сотрудник: расширение переписки запрещено.")
        if options["enable_results"]:
            role=Role.objects.filter(pk=stable_id("workflow-demo:role:Эксперт")).first()
            allowed=[stable_id("workflow-demo:employee:demo."+login) for login in ("expert","expert2","trainee")]
            if role and role.assignments.exclude(employee_id__in=allowed).exists():
                raise CommandError("В учебной роли есть неучебный сотрудник: автоматическое расширение запрещено.")
        for login,template,position_code in profiles:
            username="demo."+login;user_id=stable_id("workflow-demo:user:"+username)
            user=User.objects.filter(pk=user_id).first()
            if user is None:
                if User.objects.filter(username=username).exists():raise CommandError(f"Логин {username} занят другой учётной записью.")
                password=os.getenv("AIS_DEMO_PASSWORD","")
                try:validate_password(password,User(username=username))
                except ValidationError as exc:raise CommandError("AIS_DEMO_PASSWORD: "+"; ".join(exc.messages)) from exc
                user=User.objects.create_user(id=user_id,username=username,password=password)
            employee,_=Employee.objects.get_or_create(id=stable_id("workflow-demo:employee:"+username),defaults={"user":user,"full_name":f"ДЕМО · {template} ({login})"})
            position,_=Position.objects.get_or_create(code=position_code,defaults={"name":template})
            EmployeeOrgAssignment.objects.get_or_create(id=stable_id("workflow-demo:org:"+username),defaults={"employee":employee,"department":department,"position":position,"reason":"Учебный профиль, не реальный сотрудник учреждения"})
            role,created=Role.objects.get_or_create(id=stable_id("workflow-demo:role:"+template),defaults={"name":"ДЕМО · "+template,"description":"Только учебные профили локального окружения"})
            if created:RolePermission.objects.bulk_create([RolePermission(role=role,permission_code=code,scope=scope) for code,scope in TEMPLATES[template].items()])
            assignment,created=EmployeeRole.objects.get_or_create(id=stable_id("workflow-demo:grant:"+username),defaults={"employee":employee,"role":role,"reason":"Явный учебный профиль для проверки сквозного пути"})
            if created and template=="Руководитель отдела":assignment.departments.add(department)
            if login in ("expert","expert2","trainee"):
                EmployeeSpecialty.objects.get_or_create(employee=employee,specialty=specialty,defaults={"status":"training" if login=="trainee" else "qualified","basis":"Учебная квалификация для демонстрации, не сведения о реальном сотруднике"})
        if options["enable_results"]:
            role=Role.objects.get(pk=stable_id("workflow-demo:role:Эксперт"))
            for code in ("expertise.result.draft","expertise.return_without_execution"):
                RolePermission.objects.get_or_create(role=role,permission_code=code,defaults={"scope":"own"})
        if options["enable_correspondence"]:
            for template in ("Эксперт", "Делопроизводитель"):
                role=Role.objects.get(pk=stable_id("workflow-demo:role:"+template))
                for code, scope in CORRESPONDENCE_NEW_RIGHTS[template].items():
                    RolePermission.objects.get_or_create(role=role,permission_code=code,defaults={"scope":scope})
        if options["enable_issuance"]:
            for template in ("Эксперт", "Делопроизводитель"):
                role=Role.objects.get(pk=stable_id("workflow-demo:role:"+template))
                for code, scope in ISSUANCE_NEW_RIGHTS[template].items():
                    RolePermission.objects.get_or_create(role=role,permission_code=code,defaults={"scope":scope})
        if options["enable_import_preview"]:
            role=Role.objects.get(pk=stable_id("workflow-demo:role:Делопроизводитель"))
            for code,scope in IMPORT_PREVIEW_NEW_RIGHTS["Делопроизводитель"].items():
                RolePermission.objects.get_or_create(role=role,permission_code=code,defaults={"scope":scope})
        self.stdout.write("Учебные профили готовы: "+", ".join("demo."+p[0] for p in profiles))
