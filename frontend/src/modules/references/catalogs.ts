export const catalogs=[
 ['departments','Отделы'],['positions','Должности'],['specialties','Специальности'],['authority-types','Типы назначивших органов'],
 ['sndz-reasons','Причины СНДЗ'],['unresolved-question-reasons','Причины нерешённых вопросов'],['return-reasons','Причины без исполнения'],
 ['letter-kinds','Виды писем'],['letter-journals','Журналы переписки'],['dispatch-channels','Способы отправки'],['control-closure-reasons','Причины снятия с контроля'],['issue-methods','Способы выдачи'],
] as const
export const reportGroups=[['court','Суды'],['sk','Следственный комитет'],['mvd','МВД'],['fsb','ФСБ'],['fts','ФТС'],['fssp','ФССП'],['individual','Физические лица'],['legal','Юридические лица'],['other','Иные']] as const
export const closureRules=[['reply_sent','Ответ отправлен'],['reply_received','Ответ получен'],['withdrawn','Отозван'],['not_required','Не требуется'],['other','Иное решение']] as const
export const caseFields=[['authority_name','Назначивший орган / заявитель'],['official','Должностное лицо'],['contact','Контакты'],['case_number','Номер дела / материала'],['case_description','Сведения о деле'],['basis_text','Реквизиты основания'],['inventory','Опись материалов'],['questions_text','Поставленные вопросы']] as const
export const caseLabels:Record<string,string>={...Object.fromEntries(caseFields),authority_type:'Тип органа',authority_type_raw:'Тип в источнике',decree3214:'В рамках 3214-р',decree_document_id:'Документ 3214-р',decree_basis:'Пояснение к 3214-р'}
