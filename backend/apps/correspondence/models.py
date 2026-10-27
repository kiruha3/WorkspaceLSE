import uuid
from django.db import models


class Letter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(max_length=12, choices=[("incoming", "Входящее"), ("outgoing", "Исходящее")])
    department = models.ForeignKey("references.Department", null=True, blank=True, on_delete=models.PROTECT)
    responsible = models.ForeignKey("personnel.Employee", null=True, blank=True, related_name="letters", on_delete=models.PROTECT)
    created_by = models.ForeignKey("personnel.Employee", related_name="created_letters", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    current_revision = models.ForeignKey("LetterRevision", null=True, blank=True, related_name="current_for", on_delete=models.PROTECT)

    class Meta:
        ordering = ["-created_at", "id"]


class LetterRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    letter = models.ForeignKey(Letter, related_name="revisions", on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    kind = models.ForeignKey("references.LetterKind", null=True, blank=True, on_delete=models.PROTECT)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    sender_name = models.CharField(max_length=500, blank=True)
    external_number = models.CharField(max_length=200, blank=True)
    external_on = models.DateField(null=True, blank=True)
    document_on = models.DateField(null=True, blank=True)
    received_on = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)
    material = models.ForeignKey("intake.Material", null=True, blank=True, related_name="letter_revisions", on_delete=models.PROTECT)
    parent = models.ForeignKey(Letter, null=True, blank=True, related_name="reply_revisions", on_delete=models.PROTECT)
    reply_completeness = models.CharField(max_length=12, null=True, blank=True, choices=[("partial", "Частичный"), ("additional", "Дополнительный"), ("final", "Завершающий")])
    expertises = models.ManyToManyField("expertises.Expertise", related_name="letter_revisions", blank=True)
    actor = models.ForeignKey("personnel.Employee", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    class Meta:
        ordering = ["number", "id"]
        constraints = [models.UniqueConstraint(fields=["letter", "number"], name="unique_letter_revision_number")]


class LetterRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(LetterRevision, related_name="recipients", on_delete=models.PROTECT)
    name = models.CharField(max_length=500)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ["id"]


class LetterAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    letter = models.ForeignKey(Letter, related_name="attachments", on_delete=models.PROTECT)
    document = models.ForeignKey("documents.Document", related_name="letter_attachments", on_delete=models.PROTECT)
    actor = models.ForeignKey("personnel.Employee", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.UniqueConstraint(fields=["letter", "document"], name="unique_letter_attachment")]
