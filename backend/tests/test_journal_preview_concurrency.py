import pytest
from apps.audit.models import AuditEvent
from test_journal_preview_api import preview_setup,send_preview
from test_letter_concurrency import parallel

pytestmark=pytest.mark.django_db(transaction=True)


def test_concurrent_preview_replays_keep_one_source_snapshot(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;_,actor=preview_setup(employee_factory,grant)
    responses=parallel(actor,[lambda client:send_preview(client) for _ in range(2)])
    assert [status for status,_ in responses]==[201,201] and responses[0][1]==responses[1][1]
    from apps.imports.models import ImportBatch,ImportRow
    assert ImportBatch.objects.count()==1 and ImportRow.objects.count()==1
    assert AuditEvent.objects.filter(action="imports.preview").count()==1
    assert len([path for path in tmp_path.rglob("*") if path.is_file()])==1
