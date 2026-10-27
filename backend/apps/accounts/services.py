import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.exceptions import APIException
from apps.audit.models import AuditEvent
from .policies import can
from rest_framework.exceptions import PermissionDenied


class VersionConflict(APIException):
    status_code = 409
    default_detail = "Запись уже изменена. Обновите данные; введённые изменения не сохранены."
    default_code = "version_conflict"


def check_version(obj, expected):
    if obj.version != expected:
        raise VersionConflict()


def audit(actor, action, obj, changes, reason=""):
    return AuditEvent.objects.create(actor=actor,action=action,object_type=obj._meta.label_lower,
        object_id=str(obj.pk),changes=json.loads(json.dumps(changes,cls=DjangoJSONEncoder)),reason=reason)


def require_any(user, *actions):
    if not any(can(user,action) for action in actions):
        raise PermissionDenied("Нет права на просмотр этого справочника.")
