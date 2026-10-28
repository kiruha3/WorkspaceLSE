"""Source references are not filesystem paths or implicitly fetched content."""
from pathlib import PureWindowsPath
from urllib.parse import urlsplit
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


def validate_source_url(value):
    if any(ord(char)<32 or ord(char)==127 for char in value):
        raise ValidationError('Ссылка содержит управляющие символы.')
    try:
        URLValidator(schemes=['http','https'])(value)
        parts=urlsplit(value)
        if parts.username is not None or parts.password is not None:
            raise ValueError('credentials')
    except (ValueError,DjangoValidationError):
        raise ValidationError('Укажите HTTP/HTTPS-ссылку без логина и пароля.')
    return value


def normalize_relative_path(value,original_name):
    if not value:return ''
    path=value.replace('\\','/')
    if (len(path)>1000 or path.startswith('/') or PureWindowsPath(path).drive
        or any(part in ('','..','.') for part in path.split('/'))
        or any(ord(char)<32 or ord(char)==127 for char in path)
        or path.rsplit('/',1)[-1]!=original_name):
        raise ValidationError({'relative_path':'Нужен относительный путь выбранного файла без .., диска и управляющих символов.'})
    return path


def has_archived_evidence(document):
    return document.source_kind=='paper_original' or document.versions.exists()
