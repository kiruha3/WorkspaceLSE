"""Strong process facts plus explicit, detachable archive links."""
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError,PermissionDenied
from apps.accounts.policies import permission_scopes,AccessScope,active_employee
from apps.expertises.policies import require_work,expertise_scope_queryset
from .models import Document
from .policies import can_document,can_link_work
from .serializers import DocumentOutput


def origins_for(work,user,scopes):
    origins=[]
    def add(document,kind,pk,label,**extra):
        if document is not None:origins.append((document,{'kind':kind,'id':str(pk),'label':label,**extra}))
    add(work.receipt.basis_document,'receipt_basis',work.receipt_id,'Основание поступления')
    for event in work.deadline_events.select_related('document'):
        add(event.document,'deadline',event.pk,event.get_kind_display())
    for revision in work.result_revisions.select_related('document').prefetch_related('unresolved_allocations__document'):
        add(revision.document,'result_revision',revision.pk,f'Результат · редакция {revision.number}')
        for item in revision.unresolved_allocations.all():add(item.document,'unresolved_reason',item.pk,'Причина нерешённых вопросов')
    for closure in work.closures.select_related('document'):
        add(closure.document,'closure',closure.pk,f'Окончание · редакция {closure.number}',accepted_version_id=str(closure.accepted_version_id) if closure.accepted_version_id else None)
    details=getattr(work,'case_details',None)
    if details:add(details.decree_document,'decree3214',details.pk,'Основание 3214-р')
    classification=getattr(work,'classification',None)
    if classification:
        for item in classification.previous_conclusions.select_related('document'):
            add(item.document,'previous_conclusion',item.pk,f'Предыдущее заключение · {item.reference}')
    timing=getattr(work,'timing',None)
    if timing:
        for field,label in [('notification','Уведомление о сроке'),('request','Запрос продления'),('breach','Оценка нарушения срока')]:
            add(getattr(timing,field+'_document'),'timing_'+field,timing.pk,label)
        for item in timing.reasons.select_related('document'):add(item.document,'timing_reason',item.pk,'Причина длительного срока')
    history=getattr(work,'historical',None)
    if history:
        for item in history.unresolved_allocations.select_related('document'):add(item.document,'historical_unresolved',item.pk,'Причина вопросов перенесённого журнала')
    for link in work.document_links.filter(detached_at__isnull=True).select_related('document'):
        add(link.document,'extra',link.pk,'Дополнительный документ',note=link.note)
    letter_origins(work,user,scopes,add)
    issue_origins(work,user,scopes,add)
    return origins


def letter_origins(work,user,scopes,add):
    if not scopes.get('letters.view',AccessScope()).rules:return
    from apps.correspondence.policies import letter_scope_queryset
    letters=letter_scope_queryset(user,'letters.view',scopes)
    readable=expertise_scope_queryset(user,'expertise.view',scopes)
    full_material=not work.material.expertises.exclude(pk__in=readable).exists()
    match=Q(current_revision__expertises=work)
    if full_material:match|=Q(current_revision__material_id=work.material_id,current_revision__expertises__isnull=True)
    for letter in letters.filter(match).distinct().prefetch_related('attachments__document','registration__files__file_version__document','dispatches__files__file_version__document','dispatches__deliveries__evidence_document').select_related('receipt_fact__evidence_document'):
        for item in letter.attachments.all():add(item.document,'letter_attachment',item.pk,'Приложение переписки',letter_id=str(letter.pk))
        registration=getattr(letter,'registration',None)
        if registration:
            for item in registration.files.all():add(item.file_version.document,'letter_registered',item.pk,'Принятый файл регистрации письма',letter_id=str(letter.pk),accepted_version_id=str(item.file_version_id))
        received=getattr(letter,'receipt_fact',None)
        if received:add(received.evidence_document,'letter_receipt',received.pk,'Подтверждение получения письма',letter_id=str(letter.pk),accepted_version_id=str(received.accepted_version_id) if received.accepted_version_id else None)
        for dispatch in letter.dispatches.select_related('evidence_document'):
            add(dispatch.evidence_document,'letter_dispatch',dispatch.pk,'Подтверждение отправки',letter_id=str(letter.pk),accepted_version_id=str(dispatch.accepted_version_id) if dispatch.accepted_version_id else None)
            for item in dispatch.files.all():add(item.file_version.document,'letter_sent_file',item.pk,'Отправленный файл',letter_id=str(letter.pk),accepted_version_id=str(item.file_version_id))
            for item in dispatch.deliveries.all():add(item.evidence_document,'letter_delivery',item.pk,'Подтверждение доставки',letter_id=str(letter.pk),accepted_version_id=str(item.accepted_version_id) if item.accepted_version_id else None)


def issue_origins(work,user,scopes,add):
    if not scopes.get('issue.view',AccessScope()).rules:return
    if not expertise_scope_queryset(user,'issue.view',scopes).filter(pk=work.pk).exists():return
    from apps.issuance.models import CheckFile
    for item in work.issue_items.select_related('document','revision'):
        add(item.document,'issue_item',item.pk,f'Комплект выдачи · редакция {item.revision.number}')
    for item in CheckFile.objects.filter(item__expertise=work).select_related('document'):
        add(item.document,'issue_checked',item.pk,'Проверенный файл комплекта',accepted_version_id=str(item.accepted_version_id) if item.accepted_version_id else None)
    from apps.issuance.policies import package_queryset
    for package in package_queryset(user,scopes=scopes).filter(material_id=work.material_id).select_related('issuance__evidence_document'):
        issue=getattr(package,'issuance',None)
        if issue:add(issue.evidence_document,'issue_evidence',issue.pk,'Подтверждение выдачи',accepted_version_id=str(issue.accepted_evidence_version_id) if issue.accepted_evidence_version_id else None)


def page_data(values,request):
    paginator=PageNumberPagination();page=paginator.paginate_queryset(values,request)
    return {'count':paginator.page.paginator.count,'next':paginator.get_next_link(),'previous':paginator.get_previous_link(),'results':page}


def library_data(work,user,request):
    scopes=permission_scopes(user);require_work(user,'expertise.view',work,scopes)
    if not scopes.get('documents.view',AccessScope()).rules:raise PermissionDenied('Нет права просматривать документы.')
    entries={}
    for document,origin in origins_for(work,user,scopes):
        if not can_document(user,'documents.view',document,scopes):continue
        key=str(document.pk)
        if key not in entries:entries[key]={'document':DocumentOutput(document).data,'origins':[],'extra_links':[]}
        row=entries[key]
        if origin not in row['origins']:row['origins'].append(origin)
        if origin['kind']=='extra':row['extra_links'].append({'id':origin['id'],'note':origin['note']})
    kind=request.query_params.get('kind','');search=request.query_params.get('search','').strip().casefold()
    kinds=dict(Document._meta.get_field('kind').choices)
    if kind and kind not in kinds:raise ValidationError({'kind':'Неизвестный вид документа.'})
    rows=sorted(entries.values(),key=lambda row:(row['document']['title'].casefold(),row['document']['id']))
    rows=[row for row in rows if (not kind or row['document']['kind']==kind) and (not search or search in row['document']['title'].casefold())]
    history=[]
    for link in work.document_links.filter(detached_at__isnull=False).select_related('document').order_by('-detached_at','id'):
        history.append({'id':str(link.pk),'document':DocumentOutput(link.document).data if can_document(user,'documents.view',link.document,scopes) else {'id':str(link.document_id),'restricted':True},'note':link.note,'created_at':link.created_at,'detached_at':link.detached_at,'detach_reason':link.detach_reason})
    employee=active_employee(user)
    can_create=scopes.get('documents.upload',AccessScope()).allows(employee_id=employee.pk if employee else None,department_ids=[work.department_id])
    return {**page_data(rows,request),'context':{'id':str(work.pk),'registration_number':work.registration_number,'version':work.version,'state':work.state,'material':{'id':str(work.material_id)},'department':{'id':str(work.department_id),'code':work.department.code,'name':work.department.name}},
            'can_link':can_link_work(user,'documents.link',work,scopes),'can_unlink':can_link_work(user,'documents.unlink',work,scopes),'can_create':can_create,
            'document_kinds':[{'code':code,'name':name} for code,name in kinds.items()],'detached_links':history}


def options_data(work,user,request):
    scopes=permission_scopes(user)
    if not can_link_work(user,'documents.link',work,scopes):raise PermissionDenied('Нет права прикреплять документы этой работы.')
    search=request.query_params.get('search','').strip().casefold()
    # Access precedes title matching and counting: no closed-title probe.
    values=[DocumentOutput(doc).data for doc in Document.objects.prefetch_related('versions').order_by('title','id')
            if can_document(user,'documents.view',doc,scopes) and (not search or search in doc.title.casefold())]
    return page_data(values,request)
