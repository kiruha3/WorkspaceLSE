import hashlib
import json
import pytest
from django.core.management import call_command
from io import StringIO
from apps.imports.source import parse_journal,JournalSourceError
from journal_samples import csv_source,xlsx_source,row,HEADERS


@pytest.mark.django_db
@pytest.mark.parametrize("kind",["csv","xlsx"])
def test_source_preserves_rows_and_original_hash_without_creating_business_objects(kind,django_assert_num_queries):
    content=csv_source([row(J="ДЕМО\nмногострочное описание")]) if kind=="csv" else xlsx_source([row(J="ДЕМО\nмногострочное описание")])
    with django_assert_num_queries(0):result=parse_journal(content,"journal."+kind).to_dict()
    assert result["source_sha256"]==hashlib.sha256(content).hexdigest()
    assert result["source_kind"]==kind and result["summary"]["row_count"]==1
    assert result["rows"][0]["source_row"]==4
    assert result["rows"][0]["raw"]["J"]=="ДЕМО\nмногострочное описание"
    assert result["rows"][0]["facts"]["completed_on"]=="2026-03-06"
    if kind=="xlsx":assert result["sheet_name"]=="Лист1"


def test_csv_bom_semicolon_and_literal_formula_are_not_executed():
    result=parse_journal(csv_source([row(J='=HYPERLINK("не исполнять")')],delimiter=";"),"journal.csv")
    assert result.rows[0].raw["J"]=='=HYPERLINK("не исполнять")'
    assert result.rows[0].formulas=={}


def test_template_numbers_and_duration_formulas_are_not_registrations_but_missing_b_row_is_kept():
    result=parse_journal(xlsx_source([row(),{"A":2,"Z":0},{"C":"01.03.2026","L":"ДЕМО"}],formula={"Z5":("1-1",0)}),"journal.xlsx")
    assert [item.source_row for item in result.rows]==[4,6]
    assert "registration_invalid" in [d.code for d in result.rows[1].diagnostics]


def test_xlsx_caches_and_formulas_are_kept_separate_and_second_sheet_is_ignored():
    result=parse_journal(xlsx_source([row(Q=2)],formula={"Q4":("1+1",2)}),"journal.xlsx")
    assert len(result.rows)==1
    assert result.rows[0].raw["Q"]=="2" and result.rows[0].formulas=={"Q":"=1+1"}
    assert result.rows[0].facts["questions"]==2
    assert any(d.code=="formula_cached" and d.columns==["Q"] for d in result.rows[0].diagnostics)


def test_xlsx_1904_epoch_changes_serial_interpretation():
    result=parse_journal(xlsx_source([row(C=1,P=2)],date1904=True),"journal.xlsx")
    assert result.to_dict()["date_system"]=="1904"
    assert result.rows[0].facts["received_on"]=="1904-01-02"
    assert result.rows[0].facts["completed_on"]=="1904-01-03"


def test_formula_without_cache_stays_unknown_with_an_explicit_warning():
    result=parse_journal(xlsx_source([row(Q=2)],formula={"Q4":("1+1",None)}),"journal.xlsx")
    assert result.rows[0].raw["Q"] is None and result.rows[0].facts["questions"] is None
    assert any(d.code=="formula_cache_missing" and d.columns==["Q"] for d in result.rows[0].diagnostics)


def test_extra_nonempty_columns_are_not_silently_dropped():
    result=parse_journal(csv_source([row(AC="Новая неизвестная колонка")]),"journal.csv")
    assert result.rows[0].extra=={"AC":"Новая неизвестная колонка"}
    assert "unknown_columns" in [item.code for item in result.rows[0].diagnostics]


@pytest.mark.parametrize("content,name",[(b"bad","source.xls"),(b"bad","source.xlsx"),(b"\xff\xfe","source.csv"),(b'"unterminated',"source.csv"),(csv_source(headers={**HEADERS,"M":"Изменённый столбец"}),"source.csv"),(csv_source([]),"source.csv")])
def test_bad_sources_fail_with_a_user_error_without_partial_result(content,name):
    with pytest.raises(JournalSourceError):parse_journal(content,name)


def test_reader_rejects_size_expansion_and_dtd_before_loading_workbook(monkeypatch):
    from apps.imports import source
    monkeypatch.setattr(source,"MAX_FILE_BYTES",20)
    with pytest.raises(JournalSourceError):parse_journal(csv_source(),"source.csv")
    monkeypatch.setattr(source,"MAX_FILE_BYTES",20*1024*1024)
    monkeypatch.setattr(source,"MAX_EXPANDED_BYTES",10)
    with pytest.raises(JournalSourceError):parse_journal(xlsx_source(),"source.xlsx")
    monkeypatch.setattr(source,"MAX_EXPANDED_BYTES",64*1024*1024)
    with pytest.raises(JournalSourceError):parse_journal(xlsx_source(extra_xml={"xl/test.xml":'<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>'}),"source.xlsx")


def test_reader_bounds_rows_and_columns_without_truncating_a_source(monkeypatch):
    from apps.imports import source
    monkeypatch.setattr(source,"MAX_ROWS",4)
    with pytest.raises(JournalSourceError):parse_journal(csv_source([row(),row(B="152/4-1-26")]),"source.csv")
    monkeypatch.setattr(source,"MAX_ROWS",10003)
    monkeypatch.setattr(source,"MAX_COLUMNS",27)
    with pytest.raises(JournalSourceError):parse_journal(csv_source(),"source.csv")


def test_cli_defaults_to_summary_and_never_prints_case_text(tmp_path):
    path=tmp_path/"sample.csv";path.write_bytes(csv_source([row(J="ДЕМО · текст дела не для общего лога")]))
    out=StringIO();call_command("preview_journal",str(path),stdout=out)
    result=json.loads(out.getvalue())
    assert result["summary"]["row_count"]==1 and "rows" not in result
    assert "текст дела" not in out.getvalue()
    out=StringIO();call_command("preview_journal",str(path),include_rows=True,stdout=out)
    assert json.loads(out.getvalue())["rows"][0]["raw"]["J"]=="ДЕМО · текст дела не для общего лога"


def test_stale_xlsx_dimensions_never_hide_rows_or_columns():
    content=xlsx_source([row(Q=2),row(B="152/4-1-26"),row(B="153/4-1-26")],dimension="A1:P4")
    parsed=parse_journal(content,"journal.xlsx")
    assert [item.source_row for item in parsed.rows]==[4,5,6]
    assert parsed.rows[0].raw["Q"]=="2" and parsed.rows[0].facts["questions"]==2


@pytest.mark.parametrize("limit",["rows","columns"])
def test_stale_xlsx_dimensions_do_not_bypass_actual_limits(monkeypatch,limit):
    from apps.imports import source
    if limit=="rows":
        monkeypatch.setattr(source,"MAX_ROWS",4)
        content=xlsx_source([row(),row(B="152/4-1-26")],dimension="A1:AB4")
    else:
        content=xlsx_source([row(AC="За границей")],dimension="A1:AB4")
        monkeypatch.setattr(source,"MAX_COLUMNS",28)
    with pytest.raises(JournalSourceError):parse_journal(content,"journal.xlsx")


def test_uncached_business_formula_keeps_row_but_template_formula_does_not():
    content=xlsx_source([row(),{"C":0},{"A":3,"Z":0}],formula={"C5":("1+1",None),"Z6":("1-1",None)})
    parsed=parse_journal(content,"journal.xlsx")
    assert [item.source_row for item in parsed.rows]==[4,5]
    item=parsed.rows[1]
    assert item.raw["C"] is None and item.formulas=={"C":"=1+1"}
    assert {"registration_invalid","formula_cache_missing"} <= {d.code for d in item.diagnostics}


@pytest.mark.parametrize("serial,normal1900,normal1904",[(59,"1900-02-28","1904-02-29"),(60,None,"1904-03-01"),(61,"1900-03-01","1904-03-02")])
@pytest.mark.parametrize("date1904",[False,True])
@pytest.mark.parametrize("cached",[False,True])
def test_date_formatted_serials_keep_original_and_reject_phantom_1900_date(serial,normal1900,normal1904,date1904,cached):
    content=xlsx_source([row(C=serial,P=serial)],date1904=date1904,date_styles={"C4","P4"},formula={"P4":("30+30",serial)} if cached else None)
    item=parse_journal(content,"journal.xlsx").rows[0]
    assert item.raw["C"]==str(serial) and item.raw["P"]==str(serial)
    expected=normal1904 if date1904 else normal1900
    assert item.facts["received_on"]==expected and item.facts["completed_on"]==expected
    if expected is None:assert {tuple(d.columns) for d in item.diagnostics if d.code=="date_invalid"}=={("C",),("P",)}
