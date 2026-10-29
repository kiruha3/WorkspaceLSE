import type { HistoryChange,ImportApplication,ImportDiagnostic,SelectionPayload } from './imports'

export interface JournalReviewRow {
 row_id:string; source_row:number; number:string; classification:'new'|'changed'|'invalid'; action:'create'|'update'
 expected_work_version:number|null; expected_source_row_id:string|null; expected_selection_version:number; proposal_hash:string
 work_id:string|null; eligible:boolean; blockers:string[]; selection:Omit<SelectionPayload,'expected_version'|'reason'>
 changes:(HistoryChange&{conflict:boolean})[]; diagnostics:ImportDiagnostic[]
}
export interface JournalReview {batch_id:string;summary:Record<'new'|'changed'|'unchanged'|'invalid',number>;results:JournalReviewRow[]}
export interface JournalReviewChoice {
 row_id:string;action:'create'|'update';expected_work_version:number|null;expected_source_row_id:string|null
 expected_selection_version:number;proposal_hash:string;accepted_fields:string[]
}
export interface JournalReviewResult {event:{id:string};batch_id:string;created_count:number;updated_count:number;applications:ImportApplication[]}
export const journalFieldLabels:Record<string,string>={
 registration_number:'Номер',historical_number:'Прежний номер',sequence:'Порядковый номер',year:'Год',category_code:'Категория дела',department_id:'Фактический отдел',
 specialty_id:'Специальность',employee_ids:'Связанные эксперты',state:'Состояние',received_on:'Дата поступления',sender_name:'Отправитель поступления',
 result_kind:'Вид результата',completed_on:'Дата окончания',return_decided_on:'Дата решения без исполнения',issued_on:'Дата выдачи',complexity_level:'Категория сложности',
 questions:'Поставлено вопросов',categorical:'Категорические ответы',probable:'Вероятные ответы',unresolved:'Не разрешено',amount:'Сумма',
 authority_type:'Вид органа',authority_name:'Орган назначения',official:'Должностное лицо',contact:'Контакты',basis_text:'Основание',case_description:'Описание дела',
 inventory:'Опись материалов',executor_raw:'Исполнитель: текст журнала',unresolved_note:'Отметка о нерешённых вопросах',unresolved_reason_raw:'Причина в журнале',notes:'Отметки',delivery:'Передача',
 appointment_nature:'Характер назначения',is_commission:'Комиссионная',complex_known:'Комплексность известна',complex_group_key:'Группа комплекса',statistics_confirmed:'Полнота статистики'
}
const values:Record<string,string>={completed:'Завершена',without_execution:'Без исполнения',in_progress:'В работе',suspended:'Приостановлена',expert_conclusion:'Заключение эксперта',research_act:'Акт экспертного исследования',sndz:'СНДЗ',primary:'Первичная',repeated:'Повторная',additional:'Дополнительная'}
export function journalValue(value:unknown){
 if(value===null||value===undefined||value===''||Array.isArray(value)&&!value.length)return 'Не заполнено'
 if(typeof value==='boolean')return value?'Да':'Нет'
 if(Array.isArray(value))return value.join(', ')
 return values[String(value)]??String(value)
}
