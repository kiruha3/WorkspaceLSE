import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import User, Role, RolePermission
from apps.accounts.management.commands.bootstrap_access import stable_id, TEMPLATES
from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeRole, EmployeeSpecialty
from apps.references.models import Department, Position, Specialty


class Command(BaseCommand):
    help="Явные учебные профили. Не назначает роли реальным сотрудникам, не создаёт записей журнала и не сбрасывает существующие пароли."

    @transaction.atomic
    def handle(self,*args,**options):
        department,_=Department.objects.get_or_create(code="3",defaults={"name":"Отдел 3"})
        specialty,_=Specialty.objects.get_or_create(code="1.1",defaults={"name":"Исследование почерка и подписей"})
        profiles=[("clerk","Делопроизводитель","clerk"),("head3","Руководитель отдела","head"),("expert","Эксперт","expert"),("expert2","Эксперт","expert"),("trainee","Эксперт","expert")]
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
        self.stdout.write("Учебные профили готовы: "+", ".join("demo."+p[0] for p in profiles))
