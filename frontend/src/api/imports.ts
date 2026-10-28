export interface ImportDiagnostic { code:string; severity:'error'|'warning'|'info'; columns:string[]; message:string }
export interface ImportSummary { row_count:number; error_rows:number; warning_rows:number; diagnostic_counts:Record<string,number>; state_counts:Record<string,number> }
export interface ImportBatch { id:string; source_name:string; source_kind:string; source_origin:'upload'|'google_csv'; origin_url:string; source_observed_at:string|null; date_system:'1900'|'1904'; source_sha256:string; sheet_name:string; parser_version:string; created_at:string; actor:{id:string;full_name:string}|null; row_count:number; summary:ImportSummary; version:number; apply_available:boolean; source_url:string }
export interface ConfiguredGoogleSource { configured:true; spreadsheet_id:string; gid:string; sheet_name:string; label:string; url:string }
export type GoogleSourceInfo={configured:false}|ConfiguredGoogleSource
export interface GooglePreviewPayload { reason:string; spreadsheet_id:string; gid:string }
export interface ImportRow { id:string; source_row:number; raw:Record<string,string|null>; formulas:Record<string,string>; extra:Record<string,string|null>; facts:Record<string,string|number|null>; diagnostics:ImportDiagnostic[]; normalization_complete:boolean }
export interface ImportPreviewResponse { event:{id:string}; batch:ImportBatch }
export interface HistoryReference { id: string; code: string; name: string; is_active: boolean }
export interface ReconciliationOptions { departments: HistoryReference[]; specialties: HistoryReference[]; employees: { id: string; full_name: string; is_active: boolean }[] }
export interface SelectionPayload {
  expected_version: number; reason: string; department_id: string; specialty_id: string | null; employee_ids: string[]
  appointment_nature: 'primary' | 'repeated' | 'additional' | null; is_commission: boolean | null
  complex_known: boolean; complex_group_key: string | null; statistics_confirmed: boolean
}
export interface ImportSelection extends Omit<SelectionPayload, 'expected_version'> { id: string; row_id: string; version: number }
export type Classification = 'new' | 'unchanged' | 'changed' | 'invalid'
export interface ReconciliationRow { row: ImportRow; classification: Classification; existing_work: { id: string; registration_number: string; version: number } | null; blockers: ImportDiagnostic[]; suggested_department: HistoryReference | null; suggested_specialty: HistoryReference | null; selection: ImportSelection | null }
export interface ApplicationPayload { reason: string; selections: { row_id: string; expected_selection_version: number }[] }
export interface ImportApplication { id: string; batch_id: string; created_at: string; created_count: number; existing_count: number; items: { row_id: string; expertise_id: string; action: 'created' | 'existing' }[] }
export const importedStates:Record<string,string>={completed:'Завершена',without_execution:'Без исполнения',in_progress:'В производстве',suspended:'Приостановлена',unknown:'Не распознано'}
export function importTime(value:string){return new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Krasnoyarsk',dateStyle:'short',timeStyle:'short'}).format(new Date(value))}
