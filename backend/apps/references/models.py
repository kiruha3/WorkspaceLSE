import uuid
from django.db import models


class Reference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True
        ordering = ["code", "id"]

    def __str__(self):
        return self.name


class Department(Reference):
    pass


class Position(Reference):
    pass


class Specialty(Reference):
    pass


class SndzReason(Reference):
    pass


class UnresolvedQuestionReason(Reference):
    pass


class ReturnReason(Reference):
    pass


class IssueMethod(Reference):
    pass


class LetterKind(Reference):
    pass


class LetterJournal(Reference):
    direction = models.CharField(max_length=12, choices=[("incoming", "Входящие"), ("outgoing", "Исходящие")])
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT)


class DispatchChannel(Reference):
    pass


class ControlClosureReason(Reference):
    rule = models.CharField(max_length=20, default="other", choices=[("reply_sent", "Ответ отправлен"), ("reply_received", "Ответ получен"), ("withdrawn", "Отозван"), ("not_required", "Не требуется"), ("other", "Иное решение")])


class AuthorityType(Reference):
    REPORT_GROUPS = [(code, name) for code, name in (
        ('court', 'Суды'), ('sk', 'Следственный комитет'), ('mvd', 'МВД'),
        ('fsb', 'ФСБ'), ('fts', 'ФТС'), ('fssp', 'ФССП'),
        ('individual', 'Физические лица'), ('legal', 'Юридические лица'), ('other', 'Иные'),
    )]
    report_group = models.CharField(max_length=20, choices=REPORT_GROUPS, null=True, blank=True)
