"""Literal owner-confirmed rules, independent of the old TS implementation."""
from importlib.util import find_spec
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from django.test import Client
from apps.imports.normalization import normalize_rows
from apps.imports.types import SourceRow
from journal_samples import row, csv_source
from test_journal_preview_api import preview_setup, send_preview


def report(records, **options):
    assert find_spec("apps.reports") is not None, "Server form151 is not implemented"
    from apps.reports.calculation import calculate
    rows = normalize_rows([SourceRow(i + 4, item, {}, {}) for i, item in enumerate(records)], date_system="1900")
    return calculate(rows, 2026, 3, **options)


def value(result, section, address):
    return next(c["value"] for c in result["cells"] if c["sheet"] == f"Раздел {section}" and c["address"] == address)


def test_six_sections_have_hand_checked_counts_and_plan():
    records = [row(N="1", Q="2", R="1", S="0", T="1 СНДЗ", E="Органы МВД России"),
        row(B="152/4-5-26", O="СНДЗ", E="Органы МВД России"),
        row(B="153/4-6-26", O="Акт экспертного исследования", N="2", Q="3", R="3", E="Физ.лица"),
        row(B="154/4-1-26", D="Без исполнения", P="", X="выдано 10.03.2026"),
        row(B="155/4-1-26", D="В работе", P="", O="")]
    result = report(records, opening_balances_complete=True)
    for sec, addr, expected in [(1,"E108",4),(1,"F108",1),(1,"J108",1),(1,"K108",1),
        (1,"Q108",1),(1,"S108",1),(1,"T108",1),(1,"V108",1),
        (2,"D107",5),(2,"E107",4),(2,"F107",4),(2,"G107",0),(2,"H107",1),
        (3,"D107",1),(4,"D107",1),(4,"O107",1),(5,"D108",1),(5,"G108",1),(5,"R108",1),
        (6,"D107",294),(6,"E107",2),(6,"F107",1),(6,"G107",1),(6,"H107",1)]:
        assert value(result,sec,addr) == expected, (sec,addr)
    assert result["status"] == "preliminary"
    assert len(result["section_coverage"]) == 8


def test_parents_do_not_double_the_total_and_common_inventory_does_not_merge_work():
    result = report([row(B=f"{n}/3-5-26",M="16.1",K="Общее заключение",Q="22",R="16",S="0",T="6") for n in (333,334,343)])
    assert value(result,2,"D57") == 66 and value(result,2,"D58") == 66
    assert value(result,2,"D107") == 66 and value(result,2,"H107") == 18


def test_stock_is_opt_in_and_future_completion_does_not_close_at_cutoff():
    records=[row(P="06.04.2026"),row(B="152/4-1-26",D="Без исполнения",P="",W="",X=""),row(B="153/4-1-26",C="01.04.2026",P="06.04.2026")]
    assert value(report(records),1,"Q108") is None
    result=report(records,opening_balances_complete=True)
    assert value(result,1,"Q108") == 2 and value(result,1,"J108") == 0
    assert value(result,1,"E108") == 2


@pytest.mark.parametrize("overrides,cell",[({"T":"1НПВ"},"H107"),({"Q":"3","R":"1","S":"","T":""},"H107"),({"Q":"2","R":"3"},"D107")])
def test_invalid_or_inconsistent_questions_are_not_zero(overrides,cell):
    result=report([row(**{"N":"1","Q":"2","R":"2","S":"0","T":"0",**overrides})])
    assert value(result,2,cell) is None
    assert any(g["code"]=="questions" and g["rows"]==[4] for g in result["gaps"])


def test_empty_parts_are_zero_only_when_known_parts_exhaust_total():
    result=report([row(Q="2",R="2",S="",T="")])
    assert value(result,2,"G107")==0 and value(result,2,"H107")==0


def test_unknown_specialty_and_bad_dates_do_not_hide_in_totals():
    assert value(report([row(M="99.9")]),1,"J108") is None
    result=report([row(P="01.01.2026")])
    assert value(result,1,"J108") is None


def test_duplicate_current_number_stops_calculation_even_with_different_history():
    assert find_spec("apps.reports") is not None, "Server form151 is not implemented"
    with pytest.raises(ValueError,match="[Пп]овтор"):
        report([row(),row(B="00151/4-1-2026 (99/10-1-25)")])


@pytest.mark.django_db
def test_api_uses_snapshot_without_business_writes_and_download_additional_permission(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path
    client,actor=preview_setup(employee_factory,grant)
    batch=send_preview(client,csv_source([row(N="1",Q="2",R="2",S="0",T="0",E="Органы МВД России")])).json()["batch"]
    url=f"/api/v1/reports/form151/?batch_id={batch['id']}&year=2026&month=3"
    assert client.get(url).status_code == 403
    grant(actor,"reports.form151.run")
    response=client.get(url);assert response.status_code==200,response.content
    data=response.json();assert data["source"]["sha256"]==batch["source_sha256"]
    assert value(data,1,"J108")==1
    assert client.get(data["download_url"]).status_code==403
    grant(actor,"reports.form151.download")
    download=client.get(data["download_url"]);assert download.status_code==200
    raw=download.content
    ns={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(BytesIO(raw)) as archive:
        title=ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        assert "Предварительный" in "".join(title.itertext())
        section=ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
        assert section.find("s:sheetData/s:row/s:c[@r='J108']/s:v",ns).text=="1"
        assert section.find("s:sheetData/s:row/s:c[@r='G108']/s:v",ns) is None
        assert len(ET.fromstring(archive.read("xl/workbook.xml")).find("s:sheets",ns))==9
    from apps.expertises.models import Expertise
    assert Expertise.objects.count()==0
    actor.role_assignments.filter(role__permissions__permission_code="imports.results.view").update(is_active=False)
    assert client.get(url).status_code==403 and client.get(data["download_url"]).status_code==403


@pytest.mark.django_db
def test_global_source_not_available_to_department_report_or_invalid_request(employee_factory,grant,settings,tmp_path):
    settings.MEDIA_ROOT=tmp_path;client,actor=preview_setup(employee_factory,grant)
    batch=send_preview(client).json()["batch"];grant(actor,"reports.form151.run","departments")
    url=f"/api/v1/reports/form151/?batch_id={batch['id']}&year=2026&month=3"
    assert client.get(url).status_code==403
    grant(actor,"reports.form151.run")
    for query in ("month=13","year=oops","opening_balances_complete=maybe","unknown=true"):
        assert client.get(url+"&"+query).status_code==400
