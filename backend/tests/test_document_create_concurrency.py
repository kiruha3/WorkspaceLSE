import pytest
from apps.documents.models import Document
from apps.audit.models import AuditEvent
from test_receipts import clerk_client
from test_letter_concurrency import parallel

pytestmark=pytest.mark.django_db(transaction=True)


def test_concurrent_metadata_replays_create_one_document_and_audit(employee_factory,grant):
    _,actor=clerk_client(employee_factory,grant)
    data={"kind":"expert_subscription","title":"ДЕМО · одновременный повтор","source_kind":"paper_original"}
    responses=parallel(actor,[lambda client:client.post("/api/v1/documents/",data,content_type="application/json",HTTP_IDEMPOTENCY_KEY="same-metadata-command") for _ in range(2)])
    assert [response[0] for response in responses]==[201,201]
    assert responses[0][1]["id"]==responses[1][1]["id"]
    assert Document.objects.count()==1
    assert AuditEvent.objects.filter(action="document.create").count()==1
