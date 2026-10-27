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


class RecordedFact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey("personnel.Employee", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]


class EvidenceFact(RecordedFact):
    evidence_document = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    accepted_version = models.ForeignKey("documents.FileVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta(RecordedFact.Meta):
        abstract = True


class LetterRegistration(RecordedFact):
    letter = models.OneToOneField(Letter, related_name="registration", on_delete=models.PROTECT)
    revision = models.ForeignKey(LetterRevision, on_delete=models.PROTECT)
    journal = models.ForeignKey("references.LetterJournal", on_delete=models.PROTECT)
    registration_number = models.CharField(max_length=200)
    registered_on = models.DateField()
    year = models.PositiveSmallIntegerField()

    class Meta(RecordedFact.Meta):
        constraints = [models.UniqueConstraint(fields=["journal", "year", "registration_number"], name="unique_letter_journal_year_number")]


class LetterRegistrationFile(models.Model):
    registration = models.ForeignKey(LetterRegistration, related_name="files", on_delete=models.PROTECT)
    file_version = models.ForeignKey("documents.FileVersion", on_delete=models.PROTECT)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["registration", "file_version"], name="unique_letter_registration_file")]


class LetterDispatch(EvidenceFact):
    letter = models.ForeignKey(Letter, related_name="dispatches", on_delete=models.PROTECT)
    sent_on = models.DateField()
    channel = models.ForeignKey("references.DispatchChannel", on_delete=models.PROTECT)
    recipients = models.ManyToManyField(LetterRecipient, related_name="dispatches")
    tracking = models.CharField(max_length=300, blank=True)
    comment = models.TextField(blank=True)


class LetterDispatchFile(models.Model):
    dispatch = models.ForeignKey(LetterDispatch, related_name="files", on_delete=models.PROTECT)
    file_version = models.ForeignKey("documents.FileVersion", on_delete=models.PROTECT)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["dispatch", "file_version"], name="unique_letter_dispatch_file")]


class LetterDelivery(EvidenceFact):
    dispatch = models.ForeignKey(LetterDispatch, related_name="deliveries", on_delete=models.PROTECT)
    recipient = models.ForeignKey(LetterRecipient, on_delete=models.PROTECT)
    delivered_on = models.DateField()

    class Meta(RecordedFact.Meta):
        constraints = [models.UniqueConstraint(fields=["dispatch", "recipient"], name="unique_letter_dispatch_recipient_delivery")]


class LetterReceipt(EvidenceFact):
    letter = models.OneToOneField(Letter, related_name="receipt_fact", on_delete=models.PROTECT)
    received_on = models.DateField()


class LetterAssignment(RecordedFact):
    letter = models.ForeignKey(Letter, related_name="assignment_history", on_delete=models.PROTECT)
    previous = models.ForeignKey("personnel.Employee", null=True, on_delete=models.PROTECT, related_name="+")
    responsible = models.ForeignKey("personnel.Employee", on_delete=models.PROTECT, related_name="+")


class ControlTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    letter = models.OneToOneField(Letter, related_name="control", on_delete=models.PROTECT)
    opened_on = models.DateField()
    due_on = models.DateField(null=True, blank=True)
    due_basis = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)


class ControlEvent(RecordedFact):
    control = models.ForeignKey(ControlTask, related_name="events", on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=[(s, s) for s in ("opened", "deadline_changed", "closed", "reopened")])
    actual_on = models.DateField()
    due_on = models.DateField(null=True, blank=True)
    due_basis = models.TextField(blank=True)
    closure_reason = models.ForeignKey("references.ControlClosureReason", null=True, blank=True, on_delete=models.PROTECT)
    reply = models.ForeignKey(Letter, null=True, blank=True, on_delete=models.PROTECT, related_name="control_decisions")
    comment = models.TextField(blank=True)
