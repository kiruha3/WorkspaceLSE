import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q,F


class ComplexGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.ForeignKey("intake.Material", related_name="complex_groups", on_delete=models.PROTECT)
    title = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Expertise(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt = models.ForeignKey("intake.Receipt", related_name="expertises", on_delete=models.PROTECT)
    material = models.ForeignKey("intake.Material", related_name="expertises", on_delete=models.PROTECT)
    registration_number = models.CharField(max_length=100, unique=True)
    historical_number = models.CharField(max_length=300, blank=True)
    sequence = models.PositiveIntegerField()
    year = models.PositiveSmallIntegerField()
    category_code = models.CharField(max_length=1, choices=[(str(n),str(n)) for n in range(1,7)])
    department = models.ForeignKey("references.Department", on_delete=models.PROTECT)
    specialty = models.ForeignKey("references.Specialty", on_delete=models.PROTECT)
    appointment_nature = models.CharField(max_length=20, choices=[(s,s) for s in ("primary","repeated","additional")])
    is_commission = models.BooleanField(default=False)
    complex_group = models.ForeignKey(ComplexGroup, null=True, blank=True, related_name="expertises", on_delete=models.PROTECT)
    state = models.CharField(max_length=25, default="in_progress", choices=[(s,s) for s in ("in_progress","suspended","completed","without_execution")])
    version = models.PositiveIntegerField(default=1)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-year","-sequence","id"]
        constraints = [models.UniqueConstraint(fields=["complex_group","specialty"], name="one_work_per_complex_specialty")]


class ExpertAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expertise = models.ForeignKey(Expertise, related_name="assignments", on_delete=models.PROTECT)
    employee = models.ForeignKey("personnel.Employee", related_name="expert_assignments", on_delete=models.PROTECT)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    qualification_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ["started_at","id"]
        constraints = [models.UniqueConstraint(fields=["expertise","employee"], condition=Q(ended_at__isnull=True), name="one_current_work_assignment")]


class Suspension(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey(Expertise,related_name="suspensions",on_delete=models.PROTECT)
    suspended_on=models.DateField()
    resumed_on=models.DateField(null=True,blank=True)
    reason=models.TextField()
    resume_reason=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_suspensions",on_delete=models.PROTECT)
    resumed_by=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="recorded_resumptions",null=True,blank=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    resumed_recorded_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        ordering=["suspended_on","created_at","id"]
        constraints=[
            models.UniqueConstraint(fields=["expertise"],condition=Q(resumed_on__isnull=True),name="one_open_work_suspension"),
            models.CheckConstraint(condition=Q(resumed_on__isnull=True)|Q(resumed_on__gte=F("suspended_on")),name="ordered_suspension_dates"),
        ]
