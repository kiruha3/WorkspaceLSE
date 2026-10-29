"""Current missing data, derived without notification records or file I/O."""
from django.db.models import F, Prefetch
from apps.documents.models import WorkDocumentLink
from apps.issuance.models import PackageItem, PackageWorkBilling
from apps.issuance.readiness import expected_items
from .models import ResultRevision, WorkClosure
from .results import latest_closure, latest_result, result_readiness
from .history import report_gaps


def completeness_queryset(queryset):
    return queryset.select_related('receipt__basis_document', 'historical').prefetch_related(
        'receipt__basis_document__versions', 'suspensions', 'deadline_events',
        Prefetch('result_revisions', queryset=ResultRevision.objects.select_related('document').prefetch_related('document__versions')),
        Prefetch('closures', queryset=WorkClosure.objects.select_related('document').prefetch_related('document__versions')),
        Prefetch('document_links', queryset=WorkDocumentLink.objects.filter(detached_at__isnull=True).select_related('document').prefetch_related('document__versions'), to_attr='active_document_links'),
        Prefetch('issue_items', queryset=PackageItem.objects.filter(revision_id=F('revision__package__current_revision_id')).select_related('document').prefetch_related('document__versions'), to_attr='current_issue_items'),
        Prefetch('issue_billing', queryset=PackageWorkBilling.objects.filter(revision_id=F('revision__package__current_revision_id')), to_attr='current_billing'),
    )


def has_reference(document, *, allow_paper=False):
    # A stored URL is a reference, not a claim that its content was downloaded.
    return document is not None and bool(document.source_url or list(document.versions.all()) or allow_paper and document.source_kind == 'paper_original')


def missing_for(work):
    missing = {}
    def add(code, message):
        missing.setdefault(code, {'code': code, 'message': message})

    extra = [item.document for item in work.active_document_links]
    basis = [work.receipt.basis_document, *[doc for doc in extra if doc.kind in ('resolution', 'decision')]]
    if not any(has_reference(doc) for doc in basis):
        add('basis_document_missing', 'Не добавлена ссылка или цифровая копия постановления/определения.')

    closure = latest_closure(work)
    history = getattr(work, 'historical', None)
    retrospective = history is not None and not history.operational
    result = latest_result(work)
    if closure and closure.result_id:
        result = next((item for item in work.result_revisions.all() if item.pk == closure.result_id), None)
    closed = work.state in ('completed', 'without_execution')
    kind = history.result_kind if retrospective else result.kind if result else None
    if retrospective:
        for issue in report_gaps(work, history):
            add(issue['code'], issue['message'])
    elif result is not None or closed:
        readiness = result_readiness(work, result)
        for issue in readiness['report_gaps']:
            add(issue['code'], issue['message'])
        if closed:
            for issue in readiness['completion_blockers']:
                add(issue['code'], issue['message'])

    if work.specialty_id is None:
        add('specialty_missing', 'Не указана специальность экспертизы.')
    if closed:
        document_kind = 'return_decision' if work.state == 'without_execution' else kind
        candidates = [closure.document if closure else None, result.document if result else None]
        candidates += [doc for doc in extra if doc.kind == document_kind]
        if not any(doc is not None and doc.kind == document_kind and has_reference(doc) for doc in candidates):
            add('result_document_missing', 'Не прикреплён документ решения без исполнения.' if work.state == 'without_execution' else 'Не прикреплён итоговый документ экспертизы.')
        if work.state == 'completed':
            facts = history if retrospective else result
            if facts is not None and facts.complexity_level is None:
                add('complexity_missing', 'Не указана категория сложности.')
        paid = work.current_billing[0].is_paid if work.current_billing else None
        items = work.current_issue_items
        labels = {'expert_subscription': 'подписка эксперта', 'cover_letter': 'сопроводительное письмо', 'notification': 'уведомление', 'invoice': 'счёт'}
        for item_kind in expected_items(work.category_code, work.state, kind, paid):
            candidates = [item.document for item in items if item.kind == item_kind]
            candidates += [doc for doc in extra if doc.kind == item_kind]
            if not any(has_reference(doc, allow_paper=True) for doc in candidates):
                add(f'pack_{item_kind}_missing', f'Не добавлено: {labels[item_kind]}.')
        if work.is_commission:
            add('commission_subscriptions_unverified', 'Проверьте отдельную подписку каждого участника комиссии.')
    return list(missing.values())
