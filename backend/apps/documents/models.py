import uuid
from django.db import models


def version_path(instance, filename):
    from pathlib import PureWindowsPath
    suffix=PureWindowsPath(filename).suffix[:16].lower()
    return f"documents/{instance.document_id}/{instance.id}{suffix}"


class Document(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=30,choices=[("resolution","Постановление"),("decision","Определение"),("deadline_agreement","Согласование срока"),("deadline_request","Запрос срока"),("expert_conclusion","Заключение эксперта"),("research_act","Акт экспертного исследования"),("sndz","Сообщение о невозможности дать заключение"),("return_decision","Решение без исполнения"),("letter","Письмо / документ переписки"),("expert_subscription","Подписка эксперта"),("cover_letter","Сопроводительное письмо"),("notification","Уведомление"),("invoice","Счёт")])
    title=models.CharField(max_length=400)
    source_kind=models.CharField(max_length=30,choices=[("paper_original","Бумажный оригинал"),("uploaded_copy","Загружаемая копия")])
    department=models.ForeignKey("references.Department",null=True,blank=True,on_delete=models.PROTECT)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    version=models.PositiveIntegerField(default=1)


class FileVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    document=models.ForeignKey(Document,related_name="versions",on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    file=models.FileField(upload_to=version_path,max_length=500)
    original_name=models.CharField(max_length=255)
    content_type=models.CharField(max_length=100)
    size=models.PositiveBigIntegerField()
    sha256=models.CharField(max_length=64)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=["number"]
        constraints=[models.UniqueConstraint(fields=["document","number"],name="unique_document_file_version")]
