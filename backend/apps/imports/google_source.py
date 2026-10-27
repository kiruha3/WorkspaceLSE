from dataclasses import dataclass
import re
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler,Request,build_opener
from django.conf import settings
from .source import MAX_FILE_BYTES,JournalSourceError


@dataclass(frozen=True)
class GoogleSource:
    spreadsheet_id:str
    gid:str
    sheet_name:str
    label:str=""

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}",self.spreadsheet_id) or not re.fullmatch(r"\d{1,10}",self.gid) or not self.sheet_name.strip():
            raise JournalSourceError("Настройка Google-источника некорректна: нужны ID, gid и название листа.")

    @property
    def url(self):
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={self.gid}"


def configured_google_source():
    identity=getattr(settings,"JOURNAL_GOOGLE_ID","")
    if not identity:return None
    return GoogleSource(identity,str(getattr(settings,"JOURNAL_GOOGLE_GID","0")),getattr(settings,"JOURNAL_GOOGLE_SHEET_NAME","Лист1"))


def require_download_url(url):
    try:
        parsed=urlsplit(url)
        if parsed.scheme=="https" and (parsed.hostname=="docs.google.com" or (parsed.hostname or "").endswith(".googleusercontent.com")) and parsed.port in (None,443) and parsed.username is None and parsed.password is None:
            return
    except ValueError:pass
    raise JournalSourceError("Google-источник перенаправил чтение на неподдерживаемый адрес.")


def fetch_google_csv(source):
    url=f"https://docs.google.com/spreadsheets/d/{source.spreadsheet_id}/export?format=csv&gid={source.gid}"
    request=Request(url,headers={"Accept":"text/csv","User-Agent":"AIS-LSE journal read-only preview"})
    try:
        with build_opener(GoogleRedirectHandler()).open(request,timeout=20) as response:
            require_download_url(response.geturl())
            if response.status!=200 or response.headers.get("Content-Type","").split(";",1)[0].strip().lower()!="text/csv":
                raise JournalSourceError("Google не вернул CSV. Проверьте доступ только для чтения к выбранному листу.")
            content=response.read(MAX_FILE_BYTES+1)
            if len(content)>MAX_FILE_BYTES:raise JournalSourceError("Размер источника превышает 20 MiB.")
            return content
    except (URLError,OSError,TimeoutError) as error:
        raise JournalSourceError("Не удалось прочитать Google-таблицу. Проверьте доступ и соединение; снимок не создан.") from error


class GoogleRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        require_download_url(newurl)
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected is not None:
            redirected.remove_header("Authorization");redirected.remove_header("Cookie")
        return redirected
