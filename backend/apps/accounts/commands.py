import hashlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError
from .models import CommandReceipt


class CommandConflict(APIException):
    status_code = 409
    default_code = "command_conflict"
    default_detail = "Этот ключ уже использован для другой команды."


@transaction.atomic
def execute_once(*, actor, action, key, payload, operation):
    if not isinstance(key,str) or not key.strip() or len(key)>100:
        raise ValidationError({"idempotency_key":"Нужен Idempotency-Key длиной до 100 символов."})
    encoded = json.dumps(payload, sort_keys=True, separators=(",",":"), cls=DjangoJSONEncoder)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    # get_or_create handles a simultaneous unique-key insert with its savepoint.
    record, _ = CommandReceipt.objects.get_or_create(actor=actor, action=action, key=key, defaults={"payload_hash":digest})
    record = CommandReceipt.objects.select_for_update().get(pk=record.pk)
    if record.payload_hash != digest: raise CommandConflict()
    if record.result is not None: return record.result
    result = operation()
    record.result = json.loads(json.dumps(result, cls=DjangoJSONEncoder))
    record.save(update_fields=["result"])
    return record.result
