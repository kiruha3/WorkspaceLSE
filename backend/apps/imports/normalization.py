"""Source facts only: no assignments, legal events or database writes."""
import re
from datetime import date,timedelta
from decimal import Decimal,InvalidOperation
from collections import defaultdict
from .types import SourceRow,NormalizedRow,Diagnostic

STATES={"завершена":"completed","в работе":"in_progress","приостановлена":"suspended","возврат без исполнения":"without_execution","завершена без исполнения":"without_execution","без исполнения":"without_execution"}
RESULTS={"заключение эксперта":"expert_conclusion","акт экспертного исследования":"research_act","сндз":"sndz"}
for spelling in ("невозможности","невозвожности","невозможмности"):
    for ending in ("дать заключение","дачи заключения"):
        RESULTS[f"сообщение о {spelling} {ending}"]="sndz"


def text(value):
    return "" if value is None else str(value).strip()


def label(value):
    return " ".join(text(value).casefold().split())


def read_date(value,date_system):
    value=text(value)
    if not value:return None
    if re.fullmatch(r"\d+(?:\.\d+)?",value):
        serial=int(Decimal(value))
        if serial>110000 or serial<0 or (date_system=="1900" and serial in (0,60)):raise ValueError("Неверная дата Excel")
        origin=date(1904,1,1) if date_system=="1904" else date(1899,12,31)
        parsed=origin+timedelta(days=serial if date_system=="1904" or serial<60 else serial-1)
        if not 1900<=parsed.year<=2200:raise ValueError("Год вне диапазона")
        return parsed.isoformat()
    match=re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})",value)
    if match:value=f"{match[3]}-{match[2]}-{match[1]}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):raise ValueError("Неверный формат даты")
    parsed=date.fromisoformat(value)
    if not 1900<=parsed.year<=2200:raise ValueError("Год вне диапазона")
    return value


def normalize_rows(rows:list[SourceRow],*,date_system:str)->list[NormalizedRow]:
    result=[]
    for row in rows:
        diagnostics=[]
        def gap(code,columns,message,severity="error"):
            diagnostics.append(Diagnostic(code,severity,columns,message))
        def date_value(column):
            try:return read_date(row.raw.get(column),date_system)
            except (ValueError,OverflowError,InvalidOperation):
                gap("date_invalid",[column],"Некорректная дата; исходное значение сохранено.");return None
        def number(column,*,positive=False,money=False,unresolved=False):
            value=text(row.raw.get(column))
            if not value:return None
            if unresolved:
                value=re.sub(r"\s+СНДЗ$","",value,flags=re.I)
            if money:value=re.sub(r"\s*(?:руб\.?|₽|р\.)$","",value,flags=re.I)
            value=value.replace("\u00a0"," ").replace("\u202f"," ")
            if re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d+)?",value):value=value.replace(" ","")
            try:
                if not re.fullmatch(r"\d+(?:[.,]\d+)?",value):raise ValueError()
                parsed=Decimal(value.replace(",","."))
                if parsed<0 or positive and parsed==0:raise ValueError()
                if money:
                    if parsed.as_tuple().exponent < -2 or parsed>Decimal("9999999999999999.99"):raise ValueError()
                    return format(parsed,".2f")
                if parsed!=parsed.to_integral() or parsed>2147483647:raise ValueError()
                return int(parsed)
            except (ValueError,InvalidOperation):
                gap("number_invalid",[column],"Нужно допустимое целое число." if not money else "Нужна неотрицательная сумма с точностью до копеек.");return None

        facts={key:None for key in ("registration_number","historical_number","sequence","department_code","category_code","year")}
        original=text(row.raw.get("B"))
        match=re.match(r"^(?:№\s*)?(\d+)\s*/\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d{4}|\d{2})(?=$|\s|\()",original)
        groups=[value.lstrip("0") or "0" for value in match.groups()] if match else []
        if match and all(len(value)<=10 for value in groups):
            sequence,department,category,year=map(int,groups)
            year=2000+year if year<100 else year
            if 0<sequence<=2147483647 and 0<department<=2147483647 and category in range(1,7) and 2000<=year<=2099:
                facts.update(registration_number=f"{sequence}/{department}-{category}-{str(year)[2:]}",sequence=sequence,department_code=str(department),category_code=str(category),year=year)
                historical=re.search(r"\(([^()]*)\)",original[match.end():])
                facts["historical_number"]=historical[1].strip() if historical else ""
        if facts["registration_number"] is None:gap("registration_invalid",["B"],"Текущий номер не распознан; номер в скобках не заменяет его.")
        state=STATES.get(label(row.raw.get("D")))
        if state is None:gap("state_unknown",["D"],"Состояние не распознано.")
        received,end=date_value("C"),date_value("P")
        if not received and not text(row.raw.get("C")):gap("received_missing",["C"],"Не указана дата поступления.")
        completed=end if state=="completed" else None
        if received and end and end<received:gap("date_order",["C","P"],"Дата окончания раньше поступления.")
        if state=="completed" and end is None:gap("completion_date_missing",["P"],"Завершение отмечено, но дата окончания неизвестна.","warning")
        if state=="without_execution" and end:gap("return_end_meaning",["P"],"Уточните смысл даты P для работы без исполнения; дата решения или передачи не назначена.","warning")
        if state in ("in_progress","suspended") and end:gap("state_end_conflict",["D","P"],"У незавершённой работы заполнена дата окончания.","warning")
        if state=="suspended":gap("suspension_history_missing",["D"],"Отметка приостановки не содержит истории её дат.","warning")
        dates=[];invalid_issue=False
        for column in ("W","X"):
            note=re.fullmatch(r"(?:выдано|материалы\s+дела\s+возвращены)\s+(\d{2}\.\d{2}\.\d{4})\.?",text(row.raw.get(column)),flags=re.I)
            if note:
                try:dates.append(read_date(note[1],date_system))
                except ValueError:invalid_issue=True;gap("issued_date_invalid",[column],"В фактической отметке указана неверная дата.")
        issued=None
        if len(set(dates))>1:gap("issued_date_conflict",["W","X"],"Фактические отметки передачи имеют разные даты.")
        elif dates and not invalid_issue:
            issued=dates[0]
            if received and issued<received:gap("issued_before_received",["C","W","X"],"Передача указана раньше поступления.");issued=None
        specialty=text(row.raw.get("M")).rstrip(".") or None
        if specialty is None or not re.fullmatch(r"\d+\.\d+",specialty):gap("specialty_invalid",["M"],"Код специальности не распознан.");specialty=None
        result_kind=RESULTS.get(label(row.raw.get("O")))
        if text(row.raw.get("O")) and result_kind is None:gap("result_unknown",["O"],"Вид результата не распознан.","warning")
        if state=="completed" and result_kind is None:gap("result_missing",["O"],"Для завершённой работы не определён вид результата.","warning")
        if result_kind and facts["category_code"]:
            if (facts["category_code"]=="6")!=(result_kind=="research_act"):gap("work_family_conflict",["B","O"],"Категория текущего номера противоречит виду результата.")
        facts.update(state=state,specialty_code=specialty,received_on=received,source_end_on=end,completed_on=completed,issued_on=issued,result_kind=result_kind,
            complexity_level=number("N",positive=True),questions=number("Q"),categorical=number("R"),probable=number("S"),unresolved=number("T",unresolved=True),
            unresolved_note="СНДЗ" if re.search(r"\s+СНДЗ$",text(row.raw.get("T")),flags=re.I) else "",amount=number("V",money=True),legacy_duration_days=number("Z"))
        for field,column in {"authority_type":"E","authority_name":"F","official":"G","contact":"H","basis_text":"I","case_description":"J","inventory":"K","executor_raw":"L","unresolved_reason_raw":"U","notes":"W","delivery":"X"}.items():facts[field]=text(row.raw.get(column))
        counts=[facts[key] for key in ("categorical","probable","unresolved")]
        known=sum(value for value in counts if value is not None)
        if facts["questions"] is not None and (known>facts["questions"] or all(value is not None for value in counts) and known!=facts["questions"]):gap("question_sum",["Q","R","S","T"],"Число вопросов не соответствует известным выводам.")
        for column in row.formulas:
            if row.raw.get(column) is None:gap("formula_cache_missing",[column],"Кэш формулы отсутствует; значение осталось неизвестным.","warning")
            else:gap("formula_cached",[column],"Сохранено кэшированное значение формулы; пересчёт не выполнялся.","info")
        if row.extra:gap("unknown_columns",list(row.extra),"Найдены непустые неизвестные колонки после AB.")
        result.append(NormalizedRow(row.source_row,dict(row.raw),dict(row.formulas),dict(row.extra),facts,diagnostics))
    by_number=defaultdict(list)
    for row in result:
        key=row.facts["registration_number"] or text(row.raw.get("B"))
        if key:by_number[key].append(row)
    for items in by_number.values():
        if len(items)>1:
            for row in items:row.diagnostics.append(Diagnostic("duplicate_number","error",["B"],"Один текущий номер встречается в нескольких строках источника."))
    return result
