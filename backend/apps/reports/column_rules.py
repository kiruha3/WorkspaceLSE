"""Explain the implemented calculator, not unimplemented or assumed legal rules.

Keep the rules version in export fingerprints when these interpretations change.
No domain reads here: the calculation and explanations share one source snapshot.
"""
RULES_VERSION='form151-column-rules-v2'

SOURCE_FIELDS={
 'registry':{
  'received':'Expertise.receipt.received_at — поступление в текущую организацию',
  'ended':'WorkClosure.ended_on и принятый ResultRevision; при отсутствии — HistoricalWork.completed_on / return_decided_on',
  'kind':'Принятый ResultRevision.kind; при отсутствии — HistoricalWork.result_kind',
  'category':'Expertise.category_code — категория текущего номера, не номера в скобках',
  'specialty':'Expertise.specialty.code', 'state':'Expertise.state',
  'authority':'WorkCaseDetails.authority_type.report_group; без уточнённого профиля — HistoricalWork.authority_type по точному сопоставлению',
  'questions':'Принятый ResultRevision.questions / categorical / probable / unresolved; иначе текущие HistoricalWork.questions / categorical / probable / unresolved',
  'complexity':'Принятый ResultRevision.complexity_level; иначе HistoricalWork.complexity_level',
  'sndz_reason':'Принятый ResultRevision.sndz_reason; иначе HistoricalWork.sndz_reason',
  'decree':'WorkCaseDetails.decree3214, decree_document и decree_basis — явный признак и основание',
  'allocations':'ResultRevision.unresolved_allocations / HistoricalUnresolvedAllocation, allocations_complete — полное распределение по причинам',
  'nature':'Expertise.appointment_nature — явно подтверждённый характер назначения',
  'previous':'WorkClassification.previous_complete — полнота списка прежних заключений',
  'group':'PreviousConclusion.organization_group — группа прежнего учреждения',
  'comparison':'PreviousConclusion.same_input_data и confirms_previous — сопоставимость и проверка прежних выводов',
  'return_reason':'WorkClosure.return_reason; иначе HistoricalWork.return_reason',
 },
 'journal':{
  'received':'C — дата поступления в текущую организацию',
  'ended':'P — окончание; для возврата также однозначная отметка «выдано / материалы дела возвращены ДД.ММ.ГГГГ» в W/X',
  'kind':'O — результат и категория в начале текущего номера B',
  'category':'B — категория текущего номера, не номера в скобках',
  'specialty':'M — код специальности','state':'D — состояние',
  'authority':'E — тип органа по точному сопоставлению, не свободное имя F',
  'questions':'Q — всего; R/S/T — категорические, вероятные, нерешённые',
  'complexity':'N — категория сложности',
 },
}
BASE={
 1:{
  'D':('Судебные экспертизы, принятые в текущую организацию до 1 января и не законченные к началу периода.','received state ended category kind','opening'),
  'E':('Поступившие в текущую организацию судебные экспертизы за период, независимо от будущего результата.','received category kind','received'),
  'F':('Законченные работы с полным сообщением о невозможности дать заключение (СНДЗ).','ended kind','ended'),
  'J':('Законченные судебные экспертизы с заключением эксперта. Полный СНДЗ и возврат сюда не входят.','ended kind','ended'),
  'Q':('Судебные экспертизы, поступившие не позднее конца периода и не законченные к этой дате.','received state ended category kind','closing'),
  'R':('Экспертные исследования, принятые в текущую организацию до 1 января и не законченные к началу периода.','received state ended category kind','opening'),
  'S':('Поступившие экспертные исследования за период.','received category kind','received'),
  'T':('Законченные работы с актом экспертного исследования.','ended kind','ended'),
  'U':('Законченные исследования для юридических лиц.','ended kind authority','ended'),
  'V':('Законченные исследования для физических лиц.','ended kind authority','ended'),
  'W':('Законченные исследования для иных заказчиков: известная группа не является юридическим или физическим лицом.','ended kind authority','ended'),
  'X':('Исследования, поступившие не позднее конца периода и не законченные к этой дате.','received state ended category kind','closing'),
 },
 2:{
  'D':('Сумма поставленных вопросов законченных заключений эксперта и актов исследований.','ended kind questions','ended'),
  'E':('Разрешённые вопросы: сумма категорических и вероятных ответов.','ended kind questions','ended'),
  'F':('Вопросы с категорическими ответами.','ended kind questions','ended'),
  'G':('Вопросы с вероятными ответами.','ended kind questions','ended'),
  'H':('Нерешённые вопросы внутри законченных заключений или актов; это не количество полных СНДЗ.','ended kind questions','ended'),
 },
 3:{
  'D':('Законченные заключения со сроком до 30 календарных дней включительно. Считаются обе границы: окончание − поступление + 1.','received ended kind','ended'),
  'E':('Законченные заключения со сроком от 31 до 60 календарных дней включительно. Считаются обе границы.','received ended kind','ended'),
  'F':('Законченные заключения со сроком от 61 календарного дня. Считаются обе границы.','received ended kind','ended'),
 },
 4:{
  'D':('Законченные заключения с первой категорией сложности.','ended kind complexity','ended'),
  'E':('Законченные заключения со второй категорией сложности.','ended kind complexity','ended'),
  'F':('Законченные заключения с третьей категорией сложности.','ended kind complexity','ended'),
  'G':('Законченные заключения с категорией сложности выше третьей.','ended kind complexity','ended'),
  'O':('Возврат материалов без производства экспертизы или исследования. Все подтверждённые варианты «без исполнения» учитываются вместе.','ended state','returned'),
 },
 5:{'D':('Всего законченных заключений эксперта.','ended kind','ended'),'L':('Всего законченных актов экспертных исследований.','ended kind','ended')},
 6:{
  'D':('Годовой план учреждения: 294 работы на 2026 год по подтверждению владельца. Разбивка по специальностям не задана.','','annual'),
  'E':('Всего закончено работ госзадания по категориям 1 и 5: заключения и полный СНДЗ; возвраты исключены.','ended kind category','ended'),
  'F':('Полный СНДЗ по работам госзадания категорий 1 и 5.','ended kind category','ended'),
  'G':('Заключения эксперта по работам госзадания категорий 1 и 5.','ended kind category','ended'),
  'M':('Законченные исследования в госзадании при принадлежности категориям 1 и 5; категория 6 автоматически сюда не входит.','ended kind category','ended'),
 },
}
for col,category in zip('KLMNO',('уголовным делам (1)','гражданским делам (2)','арбитражным делам (3)','административным делам / КоАП (4)','проверкам сообщений о преступлении, КУСП (5)')):
 BASE[1][col]=(f'Законченные заключения эксперта по {category}.','ended kind category','ended')
for col,name in zip('EFGHIJK',('судов','СК РФ','МВД','ФСБ','ФТС','ФССП','иных органов и заказчиков')):
 BASE[5][col]=(f'Законченные заключения эксперта для {name}.','ended kind authority','ended')
for col,name in zip('MNOPQR',('СК РФ','МВД','ФСБ','ФТС','ФССП','иных органов и заказчиков, включая суды и юридических/физических лиц')):
 BASE[5][col]=(f'Законченные акты исследований для {name}.','ended kind authority','ended')
for col,category in zip('HIJKL',('уголовным делам (1)','гражданским делам (2)','арбитражным делам (3)','административным делам / КоАП (4)','КУСП (5)')):
 BASE[6][col]=(f'Законченные заключения госзадания по {category}. Сохраняется общий фильтр категорий 1 и 5.','ended kind category','ended')

def explanations(mode):
 sources=SOURCE_FIELDS[mode];rules=[]
 period={
  'opening':'Состояние на начало 1 января выбранного года. Поступление строго раньше 1 января.',
  'closing':'Состояние на конец последнего дня выбранного месяца.',
  'received':'Дата поступления с 1 января по последний день выбранного месяца включительно.',
  'ended':'Подтверждённая дата окончания с 1 января по последний день выбранного месяца включительно.',
  'returned':'Дата решения без исполнения с 1 января по конец выбранного месяца. Физическая выдача — отдельный факт.',
  'annual':'Годовой план, не месячная доля и не фактическое выполнение.',
 }
 def add(section,column,meaning,fields,when='ended',unit='работа',unknown=(),limitations=()):
  rules.append({'section':section,'column':column,'official_column':ord(column)-ord('C'),'meaning':meaning,'unit':unit,
   'sources':[*[sources.get(f,'Подтверждённый владельцем годовой план 2026' if f=='plan' else f) for f in fields.split()],sources['specialty']], 'period':period[when],
   'unknown':['Если подходящая запись может изменить показатель, но нужные сведения неизвестны, вся зависимая ячейка остаётся пустой.',*unknown],
   'limitations':['Итог считается один раз по регистрационной работе, не сложением родительских и дочерних строк специальностей. Неизвестность не равна нулю.',*limitations]})
 for section,columns in BASE.items():
  for col,(meaning,fields,when) in columns.items():
   unknown=[];limits=[]
   if section==1 and col in 'DRQX':
    unknown.append('Без явного подтверждения полноты набора остатки не рассчитываются.')
    limits.append('Номер прежней организации в скобках не переносит работу в начальный остаток; используется поступление в текущую организацию.')
   if section==2:
    unknown.append('Отсутствуют необходимые числа либо всего вопросов не равно сумме категорических, вероятных и нерешённых.')
    limits.append('Полный СНДЗ и возврат исключены. Каждый отдельный номер комплексной работы считается по своим фактическим вопросам.')
    limits.append('Пустые R/S/T в снимке выводятся нулями только при известном Q, равном сумме известных частей. В рабочей базе пустые значения остаются неизвестными.' if mode=='journal' else 'Пустые статистические поля рабочей базы не восстанавливаются нулями.')
   if section==3:limits.append('Приостановления не вычитаются. Это календарный показатель текущего расчёта, не расчёт законного процессуального срока.'+(' Причины и подтверждения показаны в отдельных графах.' if mode=='registry' else ' Причины срока и согласования отсутствуют в снимке.'))
   if section==4 and col in 'DEFG':limits.append('Полный СНДЗ, исследования и возвраты не включаются в сложность заключений.')
   if section==4 and col=='O':limits.append('В рабочей базе дата выдачи не заменяет дату решения без исполнения.' if mode=='registry' else 'Это историческое правило чтения отметки возврата, не создание нового решения в АИС.')
   if section==5:limits.append('Тип органа не определяется по свободному названию или номеру дела. «Иные» — известная группа вне перечисленных, а не неизвестный тип.')
   if section==6:
    if col=='D':fields='plan';unknown.append('План другого года и планы по специальностям неизвестны.')
    else:limits.append('Госзадание определяется категориями 1 и 5 по правилу владельца, не признаком 3214-р и не суммой оплаты.')
   add(section,col,meaning,fields,when,unit='вопрос' if section==2 else 'работа в год' if section==6 and col=='D' else 'работа',unknown=unknown,limitations=limits)
 if mode=='registry':
  from .timing_columns import DELAY_COLUMNS,DELAY_REASON_POLICY
  policy_text={'all':'Каждая работа считается один раз в каждой указанной группе причин.','primary':'Каждая работа считается только по основной причине.'}.get(DELAY_REASON_POLICY,'Правило нескольких причин ещё не подтверждено. Используется только совпадающий результат способов «все причины» и «основная»; различие остаётся неизвестным.')
  for code,col in DELAY_COLUMNS.items():
   meaning={'research_complexity':'сложность исследований','large_material_volume':'объём материалов','expert_workload':'загруженность экспертов','long_research_methods':'длительные методики','appointing_party_deadline':'срок назначившего органа','other':'иные причины'}[code]
   add(3,col,'Законченные заключения свыше30календарных дней по причине: '+meaning+'.','received ended kind WorkTimingFacts.reasons_complete WorkTimingFacts.primary_reason TimingReason.reason.report_group',unknown=['Неполный список или несопоставленная причина не доказывают отсутствие других групп.'],limitations=[policy_text,'Паузы не вычитаются; неизвестная причина не становится «иной». Несколько причин одного report_group не умножают одну работу.'])
  add(3,'M','Законченные заключения с подтверждёнными информированием и ходатайством о продлении. Оба факта должны быть не позднее окончания.','ended kind WorkTimingFacts.notification_sent WorkTimingFacts.notification_on WorkTimingFacts.notification_document WorkTimingFacts.extension_requested WorkTimingFacts.request_on WorkTimingFacts.request_document',unknown=['Для подтверждённой отправки с неизвестной датой своевременность остаётся неизвестной.'],limitations=['Нет ограничения свыше30дней: орган мог установить меньший срок.','DeadlineEvent.request, черновик и наличие файла не заменяют подтверждение фактической отправки. Запись факта сама письмо не отправляет.'])
  add(3,'N','Законченные заключения с явно подтверждённым нарушением установленного или согласованного срока.','ended kind WorkTimingFacts.deadline_breached WorkTimingFacts.breach_basis WorkTimingFacts.breach_document',unknown=['Неизвестная оценка не считается отсутствием нарушения.'],limitations=['Нет ограничения свыше30дней. Календарный срок и отсутствие события согласования автоматически не определяют юридическую оценку.','Используется подтверждённый факт с основанием и документом, а не вручную введённое число отчёта.'])
  for col,meaning in {'G':'Вопросы за пределами специальных знаний эксперта.','H':'Объекты или материалы непригодны / недостаточны и в дополнении отказано.','I':'Современный уровень науки не позволяет ответить.'}.items():
   add(1,col,'Полные СНДЗ по причине: '+meaning,'ended kind sndz_reason',limitations=['Одна структурированная причина полного СНДЗ. Не выводится из надписи «СНДЗ» у нерешённого вопроса.'])
  add(1,'P','Законченные заключения с явно подтверждённым признаком 3214-р.','ended kind decree',unknown=['Неизвестный признак не считается «нет».'],limitations=['Категории 1 и 5 не подтверждают 3214-р. Нужны отдельный признак и основание.'])
  for col,meaning in {'I':'недостаточная разработанность методик','J':'недостаточность материалов','K':'недостаточная информативность объектов','L':'иные причины'}.items():
   add(2,col,'Нерешённые вопросы законченных заключений и исследований по причине: '+meaning+'.','ended kind questions allocations',unit='вопрос',unknown=['Распределение должно быть полным, причины — сопоставлены бланку, сумма распределения равна T.'],limitations=['Считаются количества вопросов, не число строк распределения. Полный СНДЗ не подменяет частично нерешённые вопросы.'])
  repeat_sources='ended kind nature previous'
  policy='Правило включения повторных работ с полным СНДЗ не установлено. Образец за 9 месяцев не содержит подтверждённого такого случая; зависимые значения остаются неизвестными.'
  repeat_limits=[policy,'Одна работа один раз в каждой подходящей группе, даже при нескольких предыдущих заключениях. Первичная и дополнительная не считаются повторными.']
  add(4,'H','Всего законченных повторных судебных экспертиз с заключением эксперта. Полный СНДЗ требует отдельного правила.',repeat_sources,limitations=repeat_limits)
  for present,not_confirmed,group in [('I','J','ФБУ СЭУ Минюста России'),('K','L','иных государственных СЭУ России'),('M','N','иных учреждений, организаций и частных экспертов')]:
   add(4,present,f'Повторные работы после {group}.',repeat_sources+' group',unknown=['Неполный список может доказать наличие группы, но не отсутствие. Полный список с неизвестной группой тоже не доказывает отсутствие.'],limitations=repeat_limits)
   add(4,not_confirmed,f'Из повторных после {group}: не подтвердившие предыдущие выводы по тем же исходным данным.',repeat_sources+' group comparison',unknown=['Нужны явно те же исходные данные и явно не подтверждённые выводы. Неизвестность не считается отрицанием.'],limitations=[*repeat_limits,'СНДЗ сам по себе не означает, что прежние выводы не подтвердились.'])
  for col,meaning in {'P':'нет материально-технической базы','Q':'нет эксперта нужной специальности','R':'нет специальных условий','S':'запрос назначившего органа','T':'иная причина'}.items():
   add(4,col,'Возвращено без производства по причине: '+meaning+'.','ended state return_reason',when='returned',limitations=['Одна причина принятого решения, не текстовая догадка и не причина полного СНДЗ.'])
 return sorted(rules,key=lambda r:(r['section'],r['column']))
