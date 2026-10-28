import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


def version_path(instance, filename):
    from pathlib import PureWindowsPath
    suffix=PureWindowsPath(filename).suffix[:16].lower()
    return f"documents/{instance.document_id}/{instance.id}{suffix}"


class Document(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=30,choices=[("resolution","Постановление"),("decision","Определение"),("deadline_agreement","Согласование срока"),("deadline_request","Запрос срока"),("expert_conclusion","Заключение эксперта"),("research_act","Акт экспертного исследования"),("sndz","Сообщение о невозможности дать заключение"),("return_decision","Решение без исполнения"),("letter","Письмо / документ переписки"),("expert_subscription","Подписка эксперта"),("cover_letter","Сопроводительное письмо"),("notification","Уведомление"),("invoice","Счёт"),("case_material","Материалы дела / иные документы")])
    title=models.CharField(max_length=400)
    source_kind=models.CharField(max_length=30,choices=[("paper_original","Бумажный оригинал"),("uploaded_copy","Загружаемая копия"),("external_link","Внешняя ссылка")])
    source_url=models.CharField(max_length=2048,blank=True)
    department=models.ForeignKey("references.Department",null=True,blank=True,on_delete=models.PROTECT)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    version=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.CheckConstraint(condition=(Q(source_kind="external_link")&~Q(source_url=""))|Q(source_kind__in=["paper_original","uploaded_copy"],source_url=""),name="document_source_url_consistent")]


class FileVersion(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    document=models.ForeignKey(Document,related_name="versions",on_delete=models.PROTECT)
    number=models.PositiveIntegerField()
    file=models.FileField(upload_to=version_path,max_length=500)
    original_name=models.CharField(max_length=255)
    relative_path=models.CharField(max_length=1000,blank=True)
    content_type=models.CharField(max_length=100)
    size=models.PositiveBigIntegerField()
    sha256=models.CharField(max_length=64)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=["number"]
        constraints=[models.UniqueConstraint(fields=["document","number"],name="unique_document_file_version")]


class WorkDocumentLink(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    expertise=models.ForeignKey("expertises.Expertise",related_name="document_links",on_delete=models.PROTECT)
    document=models.ForeignKey(Document,related_name="work_links",on_delete=models.PROTECT)
    note=models.TextField(blank=True)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="linked_work_documents",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    detached_at=models.DateTimeField(null=True,blank=True)
    detached_by=models.ForeignKey(settings.AUTH_USER_MODEL,related_name="detached_work_documents",null=True,blank=True,on_delete=models.PROTECT)
    detach_reason=models.TextField(blank=True)

    class Meta:
        ordering=["created_at","id"]
        constraints=[models.UniqueConstraint(fields=["expertise","document"],condition=Q(detached_at__isnull=True),name="unique_active_work_document")]
