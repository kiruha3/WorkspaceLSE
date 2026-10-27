import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, F


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="employee")
    full_name = models.CharField(max_length=220)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["full_name", "id"]


class EmployeeOrgAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, related_name="org_assignments", on_delete=models.PROTECT)
    department = models.ForeignKey("references.Department", on_delete=models.PROTECT)
    position = models.ForeignKey("references.Position", on_delete=models.PROTECT)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(valid_from__isnull=True)|Q(valid_to__isnull=True)|Q(valid_to__gte=F("valid_from")), name="ordered_employment_dates")]


class EmployeeSpecialty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, related_name="specialties", on_delete=models.PROTECT)
    specialty = models.ForeignKey("references.Specialty", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=[("training","Обучение"),("qualified","Получена"),("unknown_legacy","Не подтверждена")])
    training_started_at = models.DateField(null=True, blank=True)
    qualified_at = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    basis = models.TextField(blank=True)
    mentor = models.ForeignKey(Employee, null=True, blank=True, related_name="mentored_specialties", on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["specialty__code", "id"]
        constraints = [
            models.UniqueConstraint(fields=["employee","specialty"], name="unique_employee_specialty"),
            models.CheckConstraint(condition=Q(qualified_at__isnull=True)|Q(valid_until__isnull=True)|Q(valid_until__gte=F("qualified_at")), name="ordered_specialty_dates"),
        ]


class EmployeeRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employee, related_name="role_assignments", on_delete=models.PROTECT)
    role = models.ForeignKey("accounts.Role", related_name="assignments", on_delete=models.PROTECT)
    departments = models.ManyToManyField("references.Department", blank=True)
    scope_limit = models.CharField(max_length=20, choices=[(v,v) for v in ("own","departments","institution")], default="institution")
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(valid_from__isnull=True)|Q(valid_to__isnull=True)|Q(valid_to__gte=F("valid_from")), name="ordered_role_grant_dates")]
