"""Audited annual plans, separate from completed-work facts."""
import uuid
from django.conf import settings
from django.db import models


class StateAssignmentPlan(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    year=models.IntegerField(unique=True)
    total=models.PositiveIntegerField(null=True,blank=True)
    basis_text=models.TextField(blank=True)
    document=models.ForeignKey('documents.Document',null=True,blank=True,on_delete=models.PROTECT)
    version=models.PositiveIntegerField(default=0)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(year__gte=1900,year__lte=2200),name='report_plan_year_range')]


class StateAssignmentPlanLine(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    plan=models.ForeignKey(StateAssignmentPlan,related_name='lines',on_delete=models.PROTECT)
    specialty=models.ForeignKey('references.Specialty',on_delete=models.PROTECT)
    count=models.PositiveIntegerField(null=True,blank=True)

    class Meta:
        ordering=['specialty__code','id']
        constraints=[models.UniqueConstraint(fields=['plan','specialty'],name='unique_report_plan_specialty')]


class StateAssignmentPlanRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    plan=models.ForeignKey(StateAssignmentPlan,related_name='revisions',on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    reason=models.TextField()
    before=models.JSONField()
    after=models.JSONField()
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=['number','id']
        constraints=[models.UniqueConstraint(fields=['plan','number'],name='unique_report_plan_revision')]
