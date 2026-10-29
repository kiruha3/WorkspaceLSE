"""Administrator-managed roots; saving never touches the configured filesystem."""
from pathlib import PurePosixPath, PureWindowsPath
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.commands import execute_once
from apps.accounts.policies import require
from apps.accounts.serializers import StrictSerializer
from apps.accounts.services import audit, check_version
from .models import StorageRoot
from .storage_probe import probe_directory

MANAGE = 'documents.storage.manage'


class PathInput(StrictSerializer):
    path = serializers.CharField(max_length=2000)

    def validate_path(self, value):
        windows, posix = PureWindowsPath(value), PurePosixPath(value)
        if (any(ord(c) < 32 or ord(c) == 127 for c in value)
                or value.startswith(('\\\\?\\', '\\\\.\\', '//?/', '//./'))
                or '..' in windows.parts or '..' in posix.parts
                or not (windows.is_absolute() or (value.startswith('/') and not value.startswith('//')))):
            raise serializers.ValidationError('Укажите полный путь к серверной папке, без .. и специальных префиксов.')
        return value


class RootInput(PathInput):
    expected_version = serializers.IntegerField(min_value=0)


def root_data(year, record=None):
    return {'year': year, 'path': record.path if record else '',
            'version': record.version if record else 0, 'read_only': True}


def valid_year(year):
    if not 1900 <= year <= 9999:
        raise serializers.ValidationError({'year': 'Укажите год от 1900 до 9999.'})
    return year


@transaction.atomic
def save_root(*, actor, year, data, key):
    require(actor, MANAGE)
    def operation():
        require(actor, MANAGE)
        record, created = StorageRoot.objects.get_or_create(year=year, defaults={'path': '', 'updated_by': actor})
        record = StorageRoot.objects.select_for_update().get(pk=record.pk)
        check_version(record, data['expected_version'])
        before = root_data(year) if created else root_data(year, record)
        record.path = data['path']
        record.updated_by = actor
        record.version += 1
        record.save()
        after = root_data(year, record)
        event = audit(actor, 'documents.storage.save', record, {'before': before, 'after': after})
        return {**after, 'event': {'id': str(event.pk)}}
    return execute_once(actor=actor, action='documents.storage.save', key=key,
                        payload={'year': year, **data}, operation=operation)


class StorageView(GenericAPIView):
    def finalize_response(self, *args, **kwargs):
        response = super().finalize_response(*args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class StorageSettingsView(StorageView):
    def get(self, request, year):
        require(request.user, MANAGE)
        valid_year(year)
        return Response(root_data(year, StorageRoot.objects.filter(pk=year).first()))

    def put(self, request, year):
        require(request.user, MANAGE)
        valid_year(year)
        form = RootInput(data=request.data)
        form.is_valid(raise_exception=True)
        return Response(save_root(actor=request.user, year=year, data=form.validated_data,
                                  key=request.headers.get('Idempotency-Key')))


class StorageCheckView(StorageView):
    def post(self, request):
        require(request.user, MANAGE)
        form = PathInput(data=request.data)
        form.is_valid(raise_exception=True)
        status = probe_directory(form.validated_data['path'])
        require(request.user, MANAGE)
        return Response({'status': status, 'read_only': True})
