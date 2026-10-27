export interface ImportDiagnostic { code:string; severity:'error'|'warning'|'info'; columns:string[]; message:string }
export interface ImportSummary { row_count:number; error_rows:number; warning_rows:number; diagnostic_counts:Record<string,number>; state_counts:Record<string,number> }
export interface ImportBatch { id:string; source_name:string; source_kind:string; date_system:'1900'|'1904'; source_sha256:string; sheet_name:string; parser_version:string; created_at:string; actor:{id:string;full_name:string}|null; row_count:number; summary:ImportSummary; version:number; apply_available:false; source_url:string }
export interface ImportRow { id:string; source_row:number; raw:Record<string,string|null>; formulas:Record<string,string>; extra:Record<string,string|null>; facts:Record<string,string|number|null>; diagnostics:ImportDiagnostic[]; normalization_complete:boolean }
export interface ImportPreviewResponse { event:{id:string}; batch:ImportBatch }
export const importedStates:Record<string,string>={completed:'Завершена',without_execution:'Без исполнения',in_progress:'В производстве',suspended:'Приостановлена',unknown:'Не распознано'}
export function importTime(value:string){return new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Krasnoyarsk',dateStyle:'short',timeStyle:'short'}).format(new Date(value))}
