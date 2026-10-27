from io import BytesIO
from urllib.error import HTTPError,URLError
from urllib.request import Request
import pytest
from apps.imports.source import JournalSourceError
from apps.imports.google_source import GoogleSource,configured_google_source,fetch_google_csv,GoogleRedirectHandler
from journal_samples import csv_source


@pytest.fixture
def source_config(settings):
    settings.JOURNAL_GOOGLE_ID="DEMO_sheet_123"
    settings.JOURNAL_GOOGLE_GID="0"
    settings.JOURNAL_GOOGLE_SHEET_NAME="Лист1"


class Response(BytesIO):
    def __init__(self,body,content_type="text/csv; charset=utf-8",status=200,url="https://docs.google.com/download/csv"):
        super().__init__(body);self.headers={"Content-Type":content_type};self.status=status;self.url=url
    def geturl(self):return self.url


def transport(monkeypatch,response=None,error=None):
    from apps.imports import google_source
    class Opener:
        def open(self,request,timeout):
            assert request.full_url=="https://docs.google.com/spreadsheets/d/DEMO_sheet_123/export?format=csv&gid=0"
            assert request.get_method()=="GET" and timeout==20
            if error:raise error
            return response
    monkeypatch.setattr(google_source,"build_opener",lambda *handlers:Opener())


def test_configured_google_source_exposes_only_selected_readonly_sheet(source_config,settings):
    source=configured_google_source()
    assert source.url=="https://docs.google.com/spreadsheets/d/DEMO_sheet_123/edit#gid=0"
    assert source.sheet_name=="Лист1" and source.gid=="0"
    settings.JOURNAL_GOOGLE_ID=""
    assert configured_google_source() is None


@pytest.mark.parametrize("field,value",[("JOURNAL_GOOGLE_ID","https://other.invalid/"),("JOURNAL_GOOGLE_GID","0&other=1"),("JOURNAL_GOOGLE_SHEET_NAME","")])
def test_invalid_source_config_never_becomes_a_network_destination(source_config,settings,field,value):
    setattr(settings,field,value)
    with pytest.raises(JournalSourceError):configured_google_source()


def test_google_csv_returns_exact_bounded_export_bytes(monkeypatch):
    body=csv_source();transport(monkeypatch,Response(body))
    assert fetch_google_csv(GoogleSource("DEMO_sheet_123","0","Лист1"))==body


@pytest.mark.parametrize("content_type,status,url",[("text/html",200,"https://docs.google.com/login"),("text/csv",401,"https://docs.google.com/download"),("text/csv",200,"http://other.invalid/file")])
def test_login_and_unexpected_responses_are_not_journal_bytes(monkeypatch,content_type,status,url):
    transport(monkeypatch,Response(b"not a journal",content_type,status,url))
    with pytest.raises(JournalSourceError):fetch_google_csv(GoogleSource("DEMO_sheet_123","0","Лист1"))


@pytest.mark.parametrize("error",[TimeoutError("DEMO timeout"),URLError("DEMO offline"),HTTPError("https://docs.google.com/export",401,"Denied",{},None)])
def test_google_read_errors_are_controlled_source_errors(monkeypatch,error):
    transport(monkeypatch,error=error)
    with pytest.raises(JournalSourceError):fetch_google_csv(GoogleSource("DEMO_sheet_123","0","Лист1"))


def test_google_csv_does_not_accept_bytes_past_limit(monkeypatch):
    from apps.imports import google_source
    monkeypatch.setattr(google_source,"MAX_FILE_BYTES",8)
    transport(monkeypatch,Response(b"123456789"))
    with pytest.raises(JournalSourceError):fetch_google_csv(GoogleSource("DEMO_sheet_123","0","Лист1"))


@pytest.mark.parametrize("url",["http://docs.google.com/file","https://docs.google.com.other.invalid/file","https://127.0.0.1/file","https://user:pass@docs.google.com/file","https://docs.google.com:8443/file"])
def test_google_redirect_cannot_leave_expected_https_download_hosts(url):
    with pytest.raises(JournalSourceError):GoogleRedirectHandler().redirect_request(Request("https://docs.google.com/export"),None,302,"Found",{},url)


def test_google_download_redirect_remains_get_without_credentials():
    request=GoogleRedirectHandler().redirect_request(Request("https://docs.google.com/export"),None,302,"Found",{},"https://doc-abc.googleusercontent.com/export/a")
    assert request.full_url=="https://doc-abc.googleusercontent.com/export/a" and request.get_method()=="GET"
    assert not request.has_header("Authorization") and not request.has_header("Cookie")
