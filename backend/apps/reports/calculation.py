"""Versioned 15.1 journal preview. Never writes domain records or guesses facts."""
import calendar
from datetime import date
from apps.imports.normalization import text, label, read_date
from .reason_columns import SNDZ_COLUMNS,UNRESOLVED_COLUMNS,RETURN_COLUMNS,EXTRA_COLUMNS,unresolved_counts
from .repeat_columns import repeat_summary,GROUPS
from . import column_rules
from . import timing_columns

VERSION = "form151-journal-v1"
SPECIALTIES = {"1.1": [11], "3.1": [13,14], "13.1": [49,50], "16.1": [58,59], "16.2": [58,60], "18.1": [65], "19.1": [66,67]}
COLUMNS = {1: "D E F J K L M N O Q R S T U V W X", 2: "D E F G H", 3: "D E F", 4: "D E F G O", 5: "D E F G H I J K L M N O P Q R", 6: "D E F G H I J K L M"}
AUTHORITIES = {"арбитражные суды":"court", "суды общей юрисдикции":"court", "следственные органы ск рф":"sk", "органы мвд россии":"mvd", "органы фсб россии":"fsb", "федеральная таможенная служба россии":"fts", "органы фтс россии":"fts", "органы фссп россии":"fssp", "физ.лица":"individual", "юр.лица":"legal"}


def valid_date(value):
    try:
        return date.fromisoformat(value) if isinstance(value,str) and len(value)==10 else None
    except ValueError:
        return None


def return_date(facts, raw):
    """Owner's historical-preview rule only; NOT a domain return decision."""
    if not any(text(raw.get(c)) for c in ("P","W","X")):
        return None, False, True
    values=[]; broken=False
    if text(raw.get("P")):
        parsed=valid_date(facts.get("source_end_on"));broken=parsed is None
        if parsed:values.append(parsed)
    import re
    for column in ("W","X"):
        match=re.fullmatch(r"(?:материалы\s+дела\s+возвращены|выдано)\s+(\d{2}\.\d{2}\.\d{4})\.?",text(raw.get(column)),flags=re.I)
        if match:
            try: values.append(date.fromisoformat(read_date(match[1],"1900")))
            except ValueError: broken=True
    if broken or len(set(values))!=1:return None, True, False
    received=valid_date(facts.get("received_on"))
    if received and values[0]<received:return None, True, False
    return values[0], False, False


def calculate(rows, year, month, opening_balances_complete=False, *, mode="journal"):
    if mode not in ("journal","registry"):raise ValueError("Неизвестный источник расчёта.")
    if type(year) is not int or not 1900<=year<=2200 or type(month) is not int or not 1<=month<=12:
        raise ValueError("Укажите год 1900–2200 и месяц 1–12.")
    rows=list(rows); start=date(year,1,1); end=date(year,month,calendar.monthrange(year,month)[1])
    if not rows and mode=="journal":raise ValueError("Снимок не содержит регистраций для расчёта.")
    if mode=="journal" and not any(valid_date(r.facts.get(k)) and valid_date(r.facts[k]).year==year for r in rows for k in ("received_on","source_end_on","issued_on")):
        raise ValueError(f"В снимке нет дат за {year} год. Выберите год источника.")
    numbers=set()
    for row in rows:
        number=row.facts.get("registration_number") or text(row.raw.get("B"))
        if not number or number in numbers:raise ValueError("Повтор или пустой текущий регистрационный номер: расчёт остановлен.")
        numbers.add(number)
    physical=lambda section,r: r if section in (1,5) else r-1
    cells={};gaps={};plan=294 if year==2026 else None
    for section,columns in COLUMNS.items():
        columns=[*columns.split(),*(EXTRA_COLUMNS.get(section,()) if mode=='registry' else ())]
        for r in sorted({108,*[i for rs in SPECIALTIES.values() for i in rs]}):
            for col in columns:
                addr=f"{col}{physical(section,r)}"
                cells[section,addr]={"sheet":f"Раздел {section}","address":addr,"value":(plan if r==108 else None) if section==6 and col=="D" else 0,"rows":[]}
    def gap(code,sections,message,fields="",source_row=None):
        item=gaps.setdefault(code,{"code":code,"sections":sections,"message":message,"fields":fields,"rows":[]})
        if source_row is not None and source_row not in item["rows"]:item["rows"].append(source_row)
    for args in [
        ("reasons",[1,2,4],"Нет структурированных причин СНДЗ, нерешённых вопросов и возврата материалов.","sndz_reason, unresolved_by_reason, return_reason"),
        ("deadlines",[3],"Нет причин срока свыше 30 дней и подтверждённого согласования продления.","delay_reasons, agreed_deadline"),
        ("repeated",[4],"Нет подтверждённых признаков повторности и проверки прежних выводов.","appointment_nature, previous_conclusion"),
        ("decree3214",[1],"Нет признака выполнения по распоряжению 3214-р.","decree3214"),
        ("methodical",[7],"Учебно-методическая работа отсутствует в этом журнале.","methodical_register"),
        ("lawsuits",[8],"Иски к учреждению и выплаты отсутствуют в этом журнале.","lawsuits_register"),
        ("plan",[6],"Нет разбивки годового плана по специальностям." if plan is not None else f"Не указан годовой план на {year}.","state_assignment_plan")]:
        if mode=='journal' or args[0] not in ('reasons','decree3214','repeated','deadlines'):gap(*args)
    if not opening_balances_complete:gap("openingCoverage",[1],"Не подтверждена полнота журнала: остатки на начало и конец оставлены пустыми.","opening_balances_complete")
    for row in rows:
        f,raw=row.facts,row.raw; state=f.get("state");returned=state=="without_execution"
        received=valid_date(f.get("received_on"));completed=valid_date(f.get("source_end_on"))
        broken=bool(text(raw.get("P")) and completed is None);awaiting=False
        if returned and mode=="journal":completed,broken,awaiting=return_date(f,raw)
        if received and completed and completed<received:received=completed=None;broken=True
        if received and received>end and not broken and (not completed or completed>end):continue
        closed=(returned and not awaiting) or state=="completed"
        category=f.get("category_code")
        numbered_family=None if category is None else "research" if category=="6" else "expertise"
        kind={"expert_conclusion":"expertise","research_act":"research","sndz":"sndz"}.get(f.get("result_kind"))
        result_family=None if kind is None else "research" if kind=="research" else "expertise"
        conflict=bool(numbered_family and result_family and numbered_family!=result_family)
        family=None if conflict else numbered_family or result_family
        if conflict:
            kind=None;gap("registrationConflict",list(range(1,7)),"Категория номера противоречит виду результата.","B, O",row.source_row)
        elif kind is None:
            if family=="research":kind="research"
            elif family=="expertise" and not text(raw.get("P")) and state in ("in_progress","suspended"):kind="expertise"
        mapped=SPECIALTIES.get(f.get("specialty_code"))
        def in_period(d):return None if d is None else start<=d<=end
        def open_at(beginning):
            edge=start if beginning else end
            if received and (received>=edge if beginning else received>edge):return False
            if completed and (completed<edge if beginning else completed<=edge):return False
            if not received or broken or closed and not completed:return None
            return True
        def stock(research):return None if family is None else family==("research" if research else "expertise")
        def is_kind(target):
            if returned:return False
            if kind is None:return None
            return kind!="sndz" if target=="result" else kind==target
        def put(section,column,gates,quantity=1):
            if False in gates:return
            quantity=None if None in gates else quantity
            if not mapped:gap("specialty",list(range(1,7)),"Специальность не сопоставлена строкам бланка.","M",row.source_row)
            if None in gates:
                if not received or (not returned and (broken or closed and not completed)):
                    gap("dates",list(range(1,7)),"Нет корректной даты поступления/окончания либо нарушен порядок дат.","C, P",row.source_row)
                if returned and not completed and not awaiting:gap("returnDate",[1,4],"Нет однозначной фактической даты возврата в P/W/X.","P, W, X",row.source_row)
                if kind is None and not returned and not conflict:
                    gap("resultKind",list(range(1,7)),"Вид результата не определён или не распознан.","B, O",row.source_row)
            if not mapped and mode=="registry":
                # The institutional total is known even when its specialty is
                # not. Specialty subtotals must not silently look complete.
                for r in {i for rs in SPECIALTIES.values() for i in rs}:
                    cell=cells[section,f"{column}{physical(section,r)}"]
                    cell["value"]=None
                    if row.source_row not in cell["rows"]:cell["rows"].append(row.source_row)
            for r in [*(mapped or []),108]:
                cell=cells[section,f"{column}{physical(section,r)}"]
                if (not mapped and mode=="journal") or quantity is None:cell["value"]=None
                elif cell["value"] is not None:cell["value"]+=quantity
                if row.source_row not in cell["rows"]:cell["rows"].append(row.source_row)
        finish=None if broken else False if not completed and not closed else in_period(completed)
        expertise=is_kind("expertise");research=is_kind("research");sndz=is_kind("sndz")
        put(1,"D",[open_at(True),stock(False)]);put(1,"R",[open_at(True),stock(True)])
        put(1,"E",[in_period(received),stock(False)]);put(1,"S",[in_period(received),stock(True)])
        put(1,"F",[finish,sndz]);put(1,"J",[finish,expertise]);put(1,"T",[finish,research])
        put(1,"Q",[open_at(False),stock(False)]);put(1,"X",[open_at(False),stock(True)])
        if category is None and finish is not False and not returned:gap("caseCategory",[1,6],"Категория в текущем номере не распознана.","B",row.source_row)
        for col,code in zip("KLMNO","12345"):put(1,col,[finish,expertise,None if conflict or not category else category==code])
        state_assignment=None if category is None else category in ("1","5")
        put(6,"E",[finish,state_assignment,False if returned else None if kind is None else True])
        for col,condition in [("F",sndz),("G",expertise),("M",research)]:put(6,col,[finish,state_assignment,condition])
        for col,code in zip("HIJKL","12345"):put(6,col,[finish,state_assignment,expertise,None if conflict or not category else category==code])
        organ=f['authority_group'] if mode=='registry' and 'authority_group' in f else AUTHORITIES.get(label(f.get("authority_type")))
        for col,target in zip("UVW",("legal","individual","other")):
            match=None if organ is None else organ not in ("legal","individual") if target=="other" else organ==target
            put(1,col,[finish,research,match])
        counts=[f.get(k) for k in ("questions","categorical","probable","unresolved")]
        parts=counts[1:];known=sum(n for n in parts if n is not None)
        if mode=="journal" and counts[0] is not None and known==counts[0] and all(n is not None or not text(raw.get(col)) for n,col in zip(parts,"RST")):
            parts=[0 if n is None else n for n in parts]
        q=counts[0];cat,prob,unresolved=parts
        inconsistent=q is not None and (known>q or all(n is not None for n in parts) and q!=sum(parts))
        if finish is not False and is_kind("result") is not False and (inconsistent or None in [q,*parts]):
            gap("questions",[2],"Неизвестные или противоречивые количества вопросов Q/R/S/T.","Q, R, S, T",row.source_row)
        for col,n in zip("DEFGH",(q,None if cat is None or prob is None else cat+prob,cat,prob,unresolved)):
            put(2,col,[finish,is_kind("result")],None if inconsistent else n)
        if mode=='registry':
            decree=f.get('decree3214')
            put(1,'P',[finish,expertise],None if type(decree) is not bool else int(decree))
            if finish is not False and expertise is True and type(decree) is not bool:
                gap('decree3214',[1],'Признак выполнения по3214-р не подтверждён. Категория1/5 его не определяет.','case_details.decree3214',row.source_row)
            sndz_reason=f.get('sndz_reason');return_reason=f.get('return_reason')
            allocated=unresolved_counts(f,inconsistent=inconsistent)
            for code,col in SNDZ_COLUMNS.items():put(1,col,[finish,sndz],None if sndz_reason not in SNDZ_COLUMNS else int(sndz_reason==code))
            for code,col in UNRESOLVED_COLUMNS.items():put(2,col,[finish,is_kind('result')],None if allocated is None else allocated[code])
            for code,col in RETURN_COLUMNS.items():put(4,col,[returned,finish],None if return_reason not in RETURN_COLUMNS else int(return_reason==code))
            if finish is not False:
                if sndz is True and sndz_reason not in SNDZ_COLUMNS:gap('sndzReason',[1],'Причина полного СНДЗ не указана или не сопоставлена бланку.','ResultRevision.sndz_reason',row.source_row)
                if is_kind('result') is True and allocated is None:gap('unresolvedReasons',[2],'Нет полного согласованного распределения нерешённых вопросов по причинам бланка.','unresolved / allocations_complete / unresolved_allocations',row.source_row)
                if returned and return_reason not in RETURN_COLUMNS:gap('returnReason',[4],'Причина решения без исполнения не указана или не сопоставлена бланку.','WorkClosure.return_reason',row.source_row)
        days=(completed-received).days+1 if received and completed else None
        for col,band in zip("DEF",range(3)):
            put(3,col,[finish,expertise,None if days is None else (0 if days<=30 else 1 if days<=60 else 2)==band])
        if mode=='registry':
            long_work=None if days is None else days>30
            reasons=timing_columns.delay_counts(f,timing_columns.DELAY_REASON_POLICY)
            for code,col in timing_columns.DELAY_COLUMNS.items():put(3,col,[finish,expertise,long_work,reasons[code]])
            communication=timing_columns.communication_qualifies(f,completed)
            put(3,'M',[finish,expertise,communication])
            breached=f.get('deadline_breached')
            put(3,'N',[finish,expertise],None if type(breached) is not bool else int(breached))
            if finish is not False and expertise is not False:
                if long_work is not False and any(value is None for value in reasons.values()):
                    gap('delayReasons',[3],'Причины длительности, полнота списка, сопоставление или правило нескольких причин не подтверждены.','timing.reasons / reasons_complete / primary_reason / delay_reason_policy',row.source_row)
                if communication is None:gap('timingCommunication',[3],'Нет подтверждённых фактов и дат информирования и ходатайства. Запись запроса срока не означает отправку.','timing.notification_sent / notification_on / extension_requested / request_on',row.source_row)
                if type(breached) is not bool:gap('deadlineAssessment',[3],'Нет подтверждённой оценки нарушения установленного/согласованного срока. Календарные дни её не подменяют.','timing.deadline_breached / breach_basis / breach_document',row.source_row)
        complexity=f.get("complexity_level")
        if finish is not False and expertise is True and complexity is None:gap("complexity",[4],"Не указана допустимая категория сложности.","N",row.source_row)
        for col,band in zip("DEFG",range(1,5)):put(4,col,[finish,expertise,None if complexity is None else min(4,complexity)==band])
        if mode=='registry':
            repeat=repeat_summary(f)
            # Owner policy for full СНДЗ is pending: do not silently count or exclude it.
            countable=None if sndz is True else expertise
            gates=[finish,countable,repeat['repeated']]
            put(4,'H',gates)
            for group,(present,not_confirmed) in zip(GROUPS,(('I','J'),('K','L'),('M','N'))):
                put(4,present,[*gates,repeat['groups'][group]['present']])
                put(4,not_confirmed,[*gates,repeat['groups'][group]['not_confirmed']])
            if finish is not False and countable is not False and repeat['repeated'] is None:
                gap('repeatNature',[4],'Характер назначения не подтверждён; первичность не подставляется автоматически.','appointment_nature',row.source_row)
            if finish is not False and countable is not False and repeat['repeated'] is True and any(v is None for group in repeat['groups'].values() for v in group.values()):
                gap('previousConclusions',[4],'Не подтверждена полнота или классификация предыдущих заключений/сопоставимость исходных данных/подтверждение выводов.','classification.previous_complete / previous_conclusions',row.source_row)
            if finish is not False and sndz is True and repeat['repeated'] is not False:
                gap('repeatSndzPolicy',[4],'Включение полного СНДЗ в повторные ещё не подтверждено владельцем; значение не заменено нулём.','repeat_sndz_policy',row.source_row)
        put(4,"O",[returned,finish]);put(5,"D",[finish,expertise]);put(5,"L",[finish,research])
        for col,target in zip("EFGHIJKMNOPQR",("court","sk","mvd","fsb","fts","fssp","other","sk","mvd","fsb","fts","fssp","other")):
            for_research=col>="M"
            excluded=("sk","mvd","fsb","fts","fssp") if for_research else ("court","sk","mvd","fsb","fts","fssp")
            match=None if organ is None else organ not in excluded if target=="other" else organ==target
            put(5,col,[finish,research if for_research else expertise,match])
        if finish is not False and kind is not None and organ is None:gap("authority",[1,5],"Тип органа E не сопоставлен справочнику.","E",row.source_row)
    result_cells=list(cells.values())
    if not opening_balances_complete:
        for cell in result_cells:
            if cell["sheet"]=="Раздел 1" and cell["address"][0] in "DRQX":cell["value"]=None
    coverage=[]
    for section in range(1,9):
        group=[c for c in result_cells if c["sheet"]==f"Раздел {section}"]
        coverage.append({"section":section,"filled":sum(c["value"] is not None for c in group),"unavailable":sum(c["value"] is None for c in group),"status":"Частично" if section<=6 else "Пропущен"})
    return {"version":VERSION,"rules_version":column_rules.RULES_VERSION,"column_rules":column_rules.explanations(mode),'delay_reason_policy':timing_columns.DELAY_REASON_POLICY if mode=='registry' else None,"status":"preliminary","year":year,"month":month,"from":start.isoformat(),"to":end.isoformat(),"opening_balances_complete":opening_balances_complete,"state_assignment_annual_plan":plan,"cells":result_cells,"gaps":list(gaps.values()),"section_coverage":coverage}
