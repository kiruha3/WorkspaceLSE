"""Institution-wide Google journal source; saving never performs a remote read."""
import re
from urllib.parse import urlsplit
from django.db import transaction
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from apps.accounts.commands import execute_once
from apps.accounts.policies import require
from apps.accounts.serializers import StrictSerializer
from apps.accounts.services import audit,check_version
from .google_source import GoogleSource,configured_google_source
from .models import JournalSourceSettings

MANAGE='imports.source.manage'


def source_from_record(record):
    return GoogleSource(record.spreadsheet_id,record.gid,record.sheet_name)


def active_google_source():
    record=JournalSourceSettings.objects.filter(pk=1).first()
    return source_from_record(record) if record else configured_google_source()


def values(source,version):
    return {'url':source.url if source else '', 'gid':source.gid if source else '0',
            'sheet_name':source.sheet_name if source else 'Лист1','version':version}


def source_settings_data():
    record=JournalSourceSettings.objects.filter(pk=1).first()
    return values(source_from_record(record),record.version) if record else values(configured_google_source(),0)


class SourceSettingsInput(StrictSerializer):
    url=serializers.CharField(max_length=2000)
    gid=serializers.RegexField(r'^[0-9]{1,10}$',max_length=10)
    sheet_name=serializers.CharField(max_length=255)
    expected_version=serializers.IntegerField(min_value=0)

    def validate(self,attrs):
        try:
            parsed=urlsplit(attrs['url'])
            match=re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]{10,200})(?:/(?:edit|view))?/?',parsed.path)
            if parsed.scheme!='https' or parsed.hostname!='docs.google.com' or parsed.port not in (None,443) or parsed.username is not None or parsed.password is not None or not match:
                raise ValueError
        except ValueError:
            raise serializers.ValidationError({'url':'Укажите HTTPS-ссылку Google Sheets вида https://docs.google.com/spreadsheets/d/<id>/edit.'})
        source=GoogleSource(match.group(1),attrs['gid'],attrs['sheet_name'])
        return {**attrs,'spreadsheet_id':source.spreadsheet_id,'url':source.url}


@transaction.atomic
def save_source_settings(*,actor,data,key):
    require(actor,MANAGE)
    record,created=JournalSourceSettings.objects.get_or_create(pk=1,defaults={
        'spreadsheet_id':data['spreadsheet_id'],'gid':data['gid'],'sheet_name':data['sheet_name'],'updated_by':actor})
    record=JournalSourceSettings.objects.select_for_update().get(pk=record.pk)
    def operation():
        require(actor,MANAGE);check_version(record,data['expected_version'])
        before=values(configured_google_source(),0) if created else values(source_from_record(record),record.version)
        record.spreadsheet_id=data['spreadsheet_id'];record.gid=data['gid'];record.sheet_name=data['sheet_name']
        record.updated_by=actor;record.version+=1;record.save()
        after=values(source_from_record(record),record.version)
        event=audit(actor,'imports.source.save',record,{'before':before,'after':after})
        return {**after,'event':{'id':str(event.pk)}}
    return execute_once(actor=actor,action='imports.source.save',key=key,payload=data,operation=operation)


class GoogleSourceSettingsView(GenericAPIView):
    def get(self,request):
        require(request.user,MANAGE)
        return Response(source_settings_data())

    def put(self,request):
        require(request.user,MANAGE)
        form=SourceSettingsInput(data=request.data);form.is_valid(raise_exception=True)
        return Response(save_source_settings(actor=request.user,data=form.validated_data,key=request.headers.get('Idempotency-Key')))
