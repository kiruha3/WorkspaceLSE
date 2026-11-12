"""Settings for the separate stand. No connection to the working journal."""
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

if not AIS_STAND_MODE:  # noqa: F405
    raise ImproperlyConfigured('Set AIS_STAND_MODE=1 for this separate stand.')
if SECRET_KEY == 'local-test-key-not-for-deployment':  # noqa: F405
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before starting the stand.')
DEBUG = False
STATIC_ROOT = BASE_DIR.parent / 'staticfiles'  # noqa: F405
JOURNAL_GOOGLE_ID = ''
JOURNAL_GOOGLE_GID = ''
JOURNAL_GOOGLE_SHEET_NAME = ''
