from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from apps.accounts.commands import execute_once,CommandConflict
from apps.accounts.services import check_version,audit
from apps.expertises.production import locked_work
from apps.expertises.policies import require_work
from .models import Document,WorkDocumentLink
from .policies import can_link_work,require_document


def require_link_action(actor,action,work):
    require_work(actor,'expertise.view',work)
    if not can_link_work(actor,action,work):
        raise PermissionDenied('Нет права изменять дополнительные связи этой работы.')


@transaction.atomic
def link_document(*,actor,work_id,data,key,payload):
    work=locked_work(work_id)
    require_link_action(actor,'documents.link',work)
    targets=[work]
    if data.get('share_with_complex'):
        from apps.expertises.models import Expertise
        if not work.complex_group_id:raise ValidationError({'share_with_complex':'Работа не входит в комплексную экспертизу.'})
        targets=list(Expertise.objects.select_for_update().filter(complex_group_id=work.complex_group_id).order_by('id'))
        for target in targets:require_link_action(actor,'documents.link',target)
    document=get_object_or_404(Document.objects.select_for_update(),pk=data['document_id'])
    require_document(actor,'documents.view',document)
    def operation():
        check_version(work,data['expected_version'])
        event=None;link=None
        for target in targets:
            if target.document_links.filter(document=document,detached_at__isnull=True).exists():
                if len(targets)==1:raise CommandConflict('Документ уже связан с этой работой.')
                continue
            link=WorkDocumentLink.objects.create(expertise=target,document=document,note=data.get('note',''),actor=actor)
            target.version+=1;target.save(update_fields=['version'])
            event=audit(actor,'document.work.link',link,{'expertise_id':str(target.pk),'document_id':str(document.pk),'version':target.version,'note':link.note},data['reason'])
        if event is None:raise CommandConflict('Документ уже связан со всеми номерами комплекса.')
        return {'id':str(event.pk),'expertise_id':str(work.pk),'link_id':str(link.pk)}
    return execute_once(actor=actor,action=f'document.work.link:{work.pk}',key=key,payload=payload,operation=operation)


@transaction.atomic
def detach_document(*,actor,work_id,link_id,data,key,payload):
    work=locked_work(work_id)
    require_link_action(actor,'documents.unlink',work)
    link=get_object_or_404(WorkDocumentLink.objects.select_for_update().select_related('document'),pk=link_id,expertise=work)
    require_document(actor,'documents.view',link.document)
    def operation():
        check_version(work,data['expected_version'])
        if link.detached_at is not None:raise CommandConflict('Связь уже снята.')
        link.detached_at=timezone.now();link.detached_by=actor;link.detach_reason=data['reason']
        link.save(update_fields=['detached_at','detached_by','detach_reason'])
        work.version+=1;work.save(update_fields=['version'])
        event=audit(actor,'document.work.detach',link,{'expertise_id':str(work.pk),'document_id':str(link.document_id),'version':work.version},data['reason'])
        return {'id':str(event.pk),'expertise_id':str(work.pk),'link_id':str(link.pk)}
    return execute_once(actor=actor,action=f'document.work.detach:{work.pk}:{link.pk}',key=key,payload=payload,operation=operation)
