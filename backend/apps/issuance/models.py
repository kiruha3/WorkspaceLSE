import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


ITEM_KINDS = [("expert_subscription", "Подписка эксперта"), ("cover_letter", "Сопроводительное письмо"), ("notification", "Уведомление"), ("invoice", "Счёт"), ("other", "Иное приложение")]


class IssuePackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material = models.OneToOneField("intake.Material", related_name="issue_package", on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    current_revision = models.ForeignKey("PackageRevision", null=True, blank=True, related_name="current_for", on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]


class PackageRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(IssuePackage, related_name="revisions", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    materials_description = models.TextField(blank=True)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number", "id"]
        constraints = [models.UniqueConstraint(fields=["package", "number"], name="unique_package_revision")]


class PackageItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PackageRevision, related_name="items", on_delete=models.PROTECT)
    kind = models.CharField(max_length=25, choices=ITEM_KINDS)
    expertise = models.ForeignKey("expertises.Expertise", related_name="issue_items", on_delete=models.PROTECT)
    document = models.ForeignKey("documents.Document", related_name="issue_items", on_delete=models.PROTECT)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["kind", "id"]
        constraints = [models.UniqueConstraint(fields=["revision", "kind", "expertise"], condition=~Q(kind="other"), name="unique_issue_item_role")]


class PackageWorkBilling(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(PackageRevision, related_name="billing", on_delete=models.PROTECT)
    expertise = models.ForeignKey("expertises.Expertise", related_name="issue_billing", on_delete=models.PROTECT)
    is_paid = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["expertise_id"]
        constraints = [models.UniqueConstraint(fields=["revision", "expertise"], name="unique_issue_work_billing")]


class PackageCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(IssuePackage, related_name="checks", on_delete=models.PROTECT)
    revision = models.ForeignKey(PackageRevision, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class CheckWork(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package_check = models.ForeignKey(PackageCheck, related_name="works", on_delete=models.PROTECT)
    expertise = models.ForeignKey("expertises.Expertise", on_delete=models.PROTECT)
    closure = models.ForeignKey("expertises.WorkClosure", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["package_check", "expertise"], name="unique_checked_work")]


class CheckFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package_check = models.ForeignKey(PackageCheck, related_name="files", on_delete=models.PROTECT)
    item = models.ForeignKey(PackageItem, null=True, blank=True, on_delete=models.PROTECT)
    closure = models.ForeignKey("expertises.WorkClosure", null=True, blank=True, on_delete=models.PROTECT)
    document = models.ForeignKey("documents.Document", related_name="issue_check_files", on_delete=models.PROTECT)
    accepted_version = models.ForeignKey("documents.FileVersion", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(item__isnull=False, closure__isnull=True) | Q(item__isnull=True, closure__isnull=False), name="issue_check_file_origin")]


class MaterialIssue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.OneToOneField(IssuePackage, related_name="issuance", on_delete=models.PROTECT)
    package_check = models.ForeignKey(PackageCheck, on_delete=models.PROTECT)
    issued_on = models.DateField()
    method = models.ForeignKey("references.IssueMethod", on_delete=models.PROTECT)
    recipient_name = models.CharField(max_length=500)
    recipient_basis = models.TextField()
    tracking = models.CharField(max_length=300, blank=True)
    comment = models.TextField(blank=True)
    evidence_document = models.ForeignKey("documents.Document", null=True, blank=True, related_name="issue_evidence", on_delete=models.PROTECT)
    accepted_evidence_version = models.ForeignKey("documents.FileVersion", null=True, blank=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
