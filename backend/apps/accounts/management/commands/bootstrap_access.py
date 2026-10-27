import getpass
import os
import uuid
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.accounts.models import Role, RolePermission
from apps.accounts.services import audit
from apps.personnel.models import Employee, EmployeeOrgAssignment, EmployeeSpecialty, EmployeeRole
from apps.references.models import Department, Position, Specialty

NAMESPACE = uuid.UUID("a9f26784-714b-49f9-ae93-a5189594779a")


def stable_id(key):
    return uuid.uuid5(NAMESPACE,key)


TEMPLATES = {
    "Администратор доступа": {code:"institution" for code in ["access.roles.view","access.roles.manage","access.roles.assign","access.effective.view","users.view","users.create","users.deactivate"]},
    "Кадровый учёт": {code:"institution" for code in ["employees.view","employees.create","employees.update","employees.deactivate","employees.org_assignments.manage","specialties.training.manage","specialties.qualify","references.view","references.manage"]},
    "Эксперт": {code:"own" for code in ["employees.view","expertise.view","expertise.work.update","expertise.suspend","expertise.resume","expertise.deadline.record","expertise.complete","expertise.export","documents.view","documents.upload","letters.view","letters.draft","control.close"]},
    "Руководитель отдела": {code:"departments" for code in ["employees.view","expertise.view","expertise.assign","expertise.reassign","documents.view","documents.upload","letters.view","reports.form151.run","reports.form151.download"]},
    "Заместитель начальника отдела": {code:"departments" for code in ["employees.view","expertise.view","documents.view","letters.view"]},
    "Делопроизводитель": {code:"institution" for code in ["employees.view","expertise.view","expertise.register","expertise.suspend","expertise.resume","expertise.deadline.record","expertise.export","documents.view","documents.upload","letters.view","letters.draft","letters.register","letters.mark_sent","control.close","issue.confirm","reports.form151.run","reports.form151.download"]},
    "Руководитель учреждения": {code:"institution" for code in ["employees.view","expertise.view","documents.view","letters.view","reports.form151.run","reports.form151.download"]},
}

TEMPLATES["Делопроизводитель"].update({code:"institution" for code in ["receipts.view","receipts.create","receipts.accept","receipts.amend"]})
TEMPLATES["Руководитель отдела"]["receipts.view"]="departments"
TEMPLATES["Эксперт"].update({code:"own" for code in ("expertise.result.draft","expertise.return_without_execution")})

CORRESPONDENCE_NEW_RIGHTS = {
    "Эксперт": {code:"own" for code in ("letters.reply","letters.attach","letters.mark_received","letters.mark_delivered","control.view","control.reopen")},
    "Делопроизводитель": {code:"institution" for code in ("letters.reply","letters.attach","letters.mark_received","letters.mark_delivered","control.view","control.assign","control.reopen")},
    "Руководитель отдела": {code:"departments" for code in ("control.view","control.assign","control.reopen","letters.draft","letters.reply","letters.attach","letters.register","letters.mark_sent","letters.mark_received","letters.mark_delivered","control.close")},
}
for template, permissions in CORRESPONDENCE_NEW_RIGHTS.items():
    TEMPLATES[template].update(permissions)

ISSUANCE_NEW_RIGHTS = {
    "Эксперт": {"issue.view": "own"},
    "Делопроизводитель": {code: "institution" for code in ("issue.view", "issue.prepare", "issue.check")},
    "Руководитель отдела": {"issue.view": "departments"},
    "Заместитель начальника отдела": {"issue.view": "departments"},
    "Руководитель учреждения": {"issue.view": "institution"},
}
for template, permissions in ISSUANCE_NEW_RIGHTS.items():
    TEMPLATES[template].update(permissions)

STAFF = [
    ("Власова Т.В.","3","head",["16.1","16.2"]),
    ("Миндибекова Т.М.","3","deputy",["1.1","3.1"]),
    ("Арыштаев А.С.","3","expert",["16.1"]),
    ("Васильева К.В.","3","expert",["16.1"]),
    ("Доценко В.Ю.","3","expert",["16.1"]),
    ("Подлипаева Т.И.","3","expert",["1.1","3.1"]),
    ("Колосова Ю.О.","4","head",["19.1"]),
    ("Логинов Д.Л.","4","deputy",["18.1"]),
    ("Лалетина О.В.","4","expert",["19.1"]),
    ("Третьяков К.Р.","4","expert",["13.1"]),
]


class Command(BaseCommand):
    help = "Идемпотентное начальное наполнение. Не сбрасывает пароли, отредактированные роли и квалификации."

    def add_arguments(self,parser):
        parser.add_argument("--username",required=True)
        parser.add_argument("--full-name",required=True)
        parser.add_argument("--seed-staff",action="store_true")
        parser.add_argument("--with-personnel-role",action="store_true",help="Явно совместить администратора доступа с кадровым учётом")
        parser.add_argument("--no-input",action="store_true")

    @transaction.atomic
    def handle(self,*args,**options):
        username = options["username"].strip()
        full_name = options["full_name"].strip()
        if not username or not full_name:
            raise CommandError("Укажите непустые логин и ФИО.")
        User = get_user_model()
        user = User.objects.filter(username=username).first()
        password = None
        if user is None:
            password = os.getenv("AIS_BOOTSTRAP_PASSWORD")
            if not password and not options["no_input"]:
                password = getpass.getpass("Пароль новой учётной записи: ")
            if not password:
                raise CommandError("Задайте AIS_BOOTSTRAP_PASSWORD или введите пароль интерактивно.")
            try:
                validate_password(password,User(username=username))
            except ValidationError as exc:
                raise CommandError("; ".join(exc.messages)) from exc
        departments = {code:Department.objects.get_or_create(code=code,defaults={"name":name})[0] for code,name in [("aup","АУП"),("3","Отдел 3"),("4","Отдел 4") ]}
        positions = {code:Position.objects.get_or_create(code=code,defaults={"name":name})[0] for code,name in [("expert","Эксперт"),("head","Начальник отдела"),("deputy","Заместитель начальника отдела"),("clerk","Делопроизводитель"),("director","Руководитель учреждения")]}
        specialties = {code:Specialty.objects.get_or_create(code=code,defaults={"name":name})[0] for code,name in [
            ("1.1","Исследование почерка и подписей"),
            ("3.1","Исследование реквизитов документов"),
            ("13.1","Исследование обстоятельств дорожно-транспортного происшествия"),
            ("16.1","Исследование строительных объектов и территории"),
            ("16.2","Исследование объектов землеустройства"),
            ("18.1","Исследование транспортных средств в целях определения стоимости"),
            ("19.1","Исследование промышленных (непродовольственных) товаров в целях определения стоимости"),
        ]}
        roles = {}
        for name,permissions in TEMPLATES.items():
            role,created = Role.objects.get_or_create(id=stable_id("role:"+name),defaults={"name":name,"description":"Начальный настраиваемый шаблон. Полномочия утверждаются учреждением."})
            if created:
                RolePermission.objects.bulk_create([RolePermission(role=role,permission_code=code,scope=scope) for code,scope in permissions.items()])
            roles[name] = role
        created_user = user is None
        if created_user:
            user = User.objects.create_user(username=username,password=password)
        employee,created_employee = Employee.objects.get_or_create(user=user,defaults={"full_name":full_name})
        if created_user or created_employee:
            EmployeeRole.objects.create(employee=employee,role=roles["Администратор доступа"],reason="Явная начальная настройка")
            if options["with_personnel_role"]:
                EmployeeRole.objects.create(employee=employee,role=roles["Кадровый учёт"],reason="Явно запрошено при начальной настройке")
            audit(user,"bootstrap.account",employee,{"username":username,"personnel_role":options["with_personnel_role"]})
        if options["seed_staff"]:
            for name,department,position,codes in STAFF:
                person,created = Employee.objects.get_or_create(id=stable_id("employee:"+name),defaults={"full_name":name})
                if created:
                    EmployeeOrgAssignment.objects.create(employee=person,department=departments[department],position=positions[position],reason="Начальное наполнение: подтверждения и предложения из docs/initial-data-and-tables.md")
                    EmployeeSpecialty.objects.bulk_create([EmployeeSpecialty(employee=person,specialty=specialties[code],status="unknown_legacy",basis="Упоминание в исходном журнале; квалификация и даты требуют подтверждения.") for code in codes])
        self.stdout.write(self.style.SUCCESS(f"Начальное наполнение проверено. Учётная запись {username}: {'создана' if created_user else 'сохранена без изменения пароля и доступа'}."))
