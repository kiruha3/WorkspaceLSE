import pytest
from apps.imports.types import SourceRow
from apps.imports.normalization import normalize_rows
from journal_samples import row


def normalized(values=None,**changes):
    return normalize_rows([SourceRow(4,row(**(values or {}),**changes),{}, {})],date_system="1900")[0]


@pytest.mark.parametrize("value,want",[("Завершена","completed"),("завершена","completed"),(" В работе ","in_progress"),("Приостановлена","suspended"),("Возврат без исполнения","without_execution"),("Завершена без исполнения","without_execution"),("Без исполнения","without_execution"),("новое неизвестное",None)])
def test_state_aliases_never_merge_completed_and_without_execution(value,want):
    assert normalized(D=value).facts["state"]==want


def test_only_leading_current_number_defines_category_and_historical_is_separate():
    result=normalized(B="№ 13 / 1 - 5 - 26 от 23.01.2026 (4540/10-1-25 от 12.12.2025)")
    assert {key:result.facts[key] for key in ["registration_number","department_code","category_code","year","sequence"]}=={"registration_number":"13/1-5-26","department_code":"1","category_code":"5","year":2026,"sequence":13}
    assert result.facts["historical_number"]=="4540/10-1-25 от 12.12.2025"


@pytest.mark.parametrize("value",["191/1-126","238-1-1-26","240/-1-26","395/3/1-26","0/3-1-26","1/0-1-26","1/3-7-26","1/3-1-26ошибка","ошибка (1/3-1-26)"])
def test_nonstandard_number_is_not_repaired_from_suffix(value):
    result=normalized(B=value)
    assert result.facts["registration_number"] is None
    assert "registration_invalid" in [item.code for item in result.diagnostics]


def test_overlong_number_is_a_row_diagnostic_not_a_failed_preview():
    result=normalized(B="9"*5000+"/3-1-26")
    assert result.facts["registration_number"] is None
    assert any(d.code=="registration_invalid" for d in result.diagnostics)


def test_duplicate_canonical_numbers_mark_both_rows_not_just_the_later_one():
    results=normalize_rows([SourceRow(4,row(B="1/3-1-26"),{},{}),SourceRow(7,row(B="№ 1 / 3 - 1 - 2026 (99/1-2-25)"),{},{})],date_system="1900")
    assert all("duplicate_number" in [d.code for d in item.diagnostics] for item in results)
    assert all(not item.normalization_complete for item in results)


@pytest.mark.parametrize("value,want",[("46065","2026-02-12"),("12.02.2026","2026-02-12"),("2026-02-12","2026-02-12"),("60",None),("110000",None),("31.02.2026",None),("",None)])
def test_dates_keep_valid_values_and_reject_impossible_serial_or_calendar(value,want):
    assert normalized(C=value).facts["received_on"]==want


@pytest.mark.parametrize("note,want",[("Выдано 10.03.2026","2026-03-10"),("Материалы дела возвращены 10.03.2026.","2026-03-10"),("Запрос от 10.03.2026",None),("Не выдано 10.03.2026",None),("Планируется выдано 10.03.2026",None),("Выдано 31.02.2026",None),("",None)])
def test_pickup_is_an_independent_whole_factual_note_never_p_or_request_date(note,want):
    result=normalized(D="Без исполнения",P="",X=note)
    assert result.facts["issued_on"]==want and result.facts["completed_on"] is None


def test_conflicting_or_before_received_pickup_is_not_a_confirmed_date():
    result=normalized(W="Выдано 10.03.2026",X="Выдано 11.03.2026")
    assert result.facts["issued_on"] is None and "issued_date_conflict" in [d.code for d in result.diagnostics]
    result=normalized(X="Выдано 01.02.2026")
    assert result.facts["issued_on"] is None and "issued_before_received" in [d.code for d in result.diagnostics]
    result=normalized(P="01.02.2026")
    assert "date_order" in [d.code for d in result.diagnostics]


def test_source_end_for_return_is_preserved_without_inventing_decision_or_pickup():
    result=normalized(D="Без исполнения",P="06.03.2026")
    assert result.facts["source_end_on"]=="2026-03-06"
    assert result.facts["completed_on"] is None and result.facts["issued_on"] is None
    assert "return_end_meaning" in [d.code for d in result.diagnostics]


def test_result_kind_uses_o_not_the_unresolved_reason_in_u():
    result=normalized(O="Заключение эксперта",U="СНДЗ",T="1 СНДЗ",Q="2",R="1",S="0")
    assert result.facts["result_kind"]=="expert_conclusion"
    assert result.facts["unresolved"]==1 and result.facts["unresolved_note"]=="СНДЗ"
    assert result.facts["unresolved_reason_raw"]=="СНДЗ"


@pytest.mark.parametrize("value",["Сообщение о невозможности дать заключение","Сообщение о невозвожности дать заключение","Сообщение о невозможмности дачи заключения","СНДЗ"])
def test_known_full_sndz_spellings_are_explicitly_supported(value):
    assert normalized(O=value).facts["result_kind"]=="sndz"


def test_missing_counts_do_not_turn_into_zero_and_known_values_are_not_discarded():
    result=normalized(Q="2",R="2",S="",T="0",N="1",V="1 200,50",Z="22",M="18.1.")
    assert [result.facts[key] for key in ["questions","categorical","probable","unresolved","complexity_level","amount","specialty_code"]]==[2,2,None,0,1,"1200.50","18.1"]
    assert "objects" not in result.facts


@pytest.mark.parametrize("value",["-1","1.5","текст","2147483648"])
def test_invalid_question_count_does_not_become_a_plausible_number(value):
    result=normalized(Q=value)
    assert result.facts["questions"] is None and "number_invalid" in [d.code for d in result.diagnostics]


def test_known_count_overflow_and_work_family_conflict_are_visible():
    result=normalized(Q="2",R="2",S="1",T="0",O="Акт экспертного исследования")
    assert {d.code for d in result.diagnostics}>={"question_sum","work_family_conflict"}


def test_missing_date_result_and_multiple_names_stay_unknown_not_fake_events():
    result=normalized(P="",O="",L="ДЕМО А.А. (передано ДЕМО Б.Б.)",D="Завершена")
    assert result.facts["completed_on"] is None and result.facts["result_kind"] is None
    assert result.facts["executor_raw"]=="ДЕМО А.А. (передано ДЕМО Б.Б.)"
    assert "assignments" not in result.facts and "is_commission" not in result.facts
    assert {d.code for d in result.diagnostics}>={"completion_date_missing","result_missing"}
