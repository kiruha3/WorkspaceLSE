export type Scope = 'own' | 'departments' | 'institution'
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface AccessGrant {
  scope: Scope; scope_limit: Scope; department_ids: string[]
  role_id: string; role_name: string; assignment_id: string
}
export type Access = Record<string, AccessGrant[]>
export interface CurrentUser { id: string; username: string; employee: { id: string; full_name: string } | null; access: Access; supported_modules?: string[] }
export interface PermissionDefinition { code: string; label: string; module: string; scopes: Scope[] }
export interface RolePermission { permission_code: string; scope: Scope }
export interface Role {
  id: string; name: string; description: string; is_active: boolean; version: number
  permissions: RolePermission[]; assignment_count: number
}
export interface Reference { id: string; code: string; name: string; is_active: boolean; version: number }
export interface OrgAssignment {
  id: string; department: Pick<Reference, 'id' | 'code' | 'name'>
  position: Pick<Reference, 'id' | 'code' | 'name'>; valid_from: string | null; valid_to: string | null
  version: number; reason: string
}
export interface EmployeeSpecialty {
  id: string; specialty: Pick<Reference, 'id' | 'code' | 'name'>
  status: 'training' | 'qualified' | 'unknown_legacy'; training_started_at: string | null
  qualified_at: string | null; valid_until: string | null; basis: string; mentor_id: string | null; version: number
}
export interface Employee {
  id: string; full_name: string; is_active: boolean; version: number
  org_assignments: OrgAssignment[]; specialties: EmployeeSpecialty[]
}
export interface EmployeeRole {
  id: string; role: { id: string; name: string }; scope_limit: Scope; department_ids: string[]
  valid_from: string | null; valid_to: string | null; is_active: boolean; reason: string
  version: number
}
export interface EmployeeAccount { id: string; username: string; is_active: boolean }
export interface FileVersion {
  id: string; number: number; original_name: string; content_type: string; size: number
  sha256: string; created_at: string; download_url: string; preview_url: string | null
}
export type ResultKind = 'expert_conclusion' | 'research_act' | 'sndz'
export type DocumentKind = 'resolution' | 'decision' | 'deadline_agreement' | 'deadline_request' | ResultKind | 'return_decision' | 'letter' | 'expert_subscription' | 'cover_letter' | 'notification' | 'invoice'
export interface BasisDocument {
  accepted_version_id?: string | null
  id: string; kind: DocumentKind; title: string; source_kind: 'paper_original' | 'uploaded_copy'
  department_id: string | null; version: number; versions: FileVersion[]
}
export type DocumentLink = BasisDocument | { id: string; restricted: true } | null
export interface Receipt {
  id: string; received_at: string; sender_name: string; material: { id: string; title: string }
  basis_document: DocumentLink; department_id: string | null; status: 'draft' | 'accepted' | 'historical'; version: number
}
export interface ComplexGroup { id: string; title: string; material_id?: string }
export interface ExpertAssignment {
  id: string; employee: { id: string; full_name: string }; started_at: string; ended_at: string | null; reason: string
}
export interface AssignmentCandidate { id: string; full_name: string; eligible: boolean; code: string; message: string }
export interface Production {
  as_of: string; counted_through: string | null; method: 'calendar_inclusive_pause_half_open_v1'
  calendar_days: number | null; paused_days: number | null; active_calendar_days: number | null
  initial_due_on: string | null; agreed_due_on: string | null; current_due_on: string | null
  last_requested_due_on: string | null; overdue_calendar_days: number | null
}
export interface Suspension {
  id: string; suspended_on: string; resumed_on: string | null; reason: string; resume_reason: string
  created_at: string; resumed_recorded_at: string | null; actor: { id: string; full_name: string }
  resumed_by: { id: string; full_name: string } | null
}
export type DeadlineKind = 'initial' | 'request' | 'agreement'
export interface DeadlineEvent {
  id: string; kind: DeadlineKind; recorded_on: string; due_on: string; reason: string; created_at: string
  actor: { id: string; full_name: string }; document: DocumentLink
}
export interface ResultIssue { code: string; field: string; message: string }
export interface ResultPayload {
  kind: ResultKind | null; completed_on: string | null; document_id: string | null; complexity_level: number | null
  questions: number | null; categorical: number | null; probable: number | null; unresolved: number | null
  statistics_complete: boolean; sndz_reason_id: string | null; sndz_comment: string
  unresolved_allocations: { reason_id: string; count: number; comment: string; document_id: string | null }[]
  allocations_complete: boolean; note: string
}
export interface ResultRevision extends Omit<ResultPayload, 'document_id' | 'sndz_reason_id' | 'unresolved_allocations'> {
  id: string; number: number; document: DocumentLink; sndz_reason: Reference | null
  unresolved_allocations: { reason: Reference; count: number; comment: string; document: DocumentLink }[]
  actor: { id: string; full_name: string }; created_at: string; reason: string
}
export interface WorkClosure {
  id: string; number: number; kind: 'completed' | 'without_execution'; ended_on: string; document: DocumentLink
  result_id: string | null; return_reason: Reference | null; comment: string
  actor: { id: string; full_name: string }; created_at: string; reason: string
}
export interface ResultOptions {
  result_kinds: { code: ResultKind; name: string }[]; complexity_groups: { code: string; name: string }[]
  sndz_reasons: Reference[]; unresolved_reasons: Reference[]; return_reasons: Reference[]
}
export interface ExpertiseCommandResponse { event: { id: string }; expertise: Expertise }
export interface HistoryActivationPayload {
  expected_version: number; reason: string; basis_document_id: string; specialty_id: string
  appointment_nature: 'primary' | 'repeated' | 'additional'; is_commission: boolean; complex_known: true; complex_group_id: string | null
  suspension_history_complete: boolean; past_suspensions: { suspended_on: string; resumed_on: string; reason: string }[]; suspended_on: string | null
  result?: ResultPayload; return_data?: { decided_on: string; document_id: string; return_reason_id: string | null; comment: string }
}
export interface HistoricalWork {
  id: string; operational: boolean; complex_known: boolean; composition_known: boolean
  suspension_history_complete: boolean; statistics_confirmed: boolean
  result_kind: ResultKind | null; completed_on: string | null; return_decided_on: string | null; issued_on: string | null
  complexity_level: number | null; questions: number | null; categorical: number | null; probable: number | null; unresolved: number | null; amount: string | null
  authority_type: string; authority_name: string; official: string; contact: string; basis_text: string; case_description: string
  inventory: string; executor_raw: string; unresolved_note: string; unresolved_reason_raw: string; notes: string; delivery: string
  current_participants: { id: string; full_name: string }[]
  source: { batch_id: string; row_id: string; source_row: number; origin_url: string | null; source_observed_at: string | null }
  report_gaps: ResultIssue[]
}
export interface Expertise {
  id: string; registration_number: string; registration_department_code?: string | null; historical_number: string; sequence: number; year: number; category_code: string
  origin_kind: 'native' | 'historical'; historical: HistoricalWork | null
  department: Pick<Reference, 'id' | 'code' | 'name'>; specialty: Pick<Reference, 'id' | 'code' | 'name'> | null
  receipt: { id: string; received_at: string; status: 'draft' | 'accepted' | 'historical' }; material: { id: string; title: string }
  appointment_nature: 'primary' | 'repeated' | 'additional' | null; is_commission: boolean | null; complex_group: ComplexGroup | null
  state: 'in_progress' | 'suspended' | 'completed' | 'without_execution'; version: number
  current_assignments: ExpertAssignment[]; assignment_history: ExpertAssignment[]; allowed_actions: string[]; basis_document: DocumentLink
  production: Production; suspensions: Suspension[]; deadline_events: DeadlineEvent[]
  result: ResultRevision | null; result_history: ResultRevision[]; closure: WorkClosure | null; closure_history: WorkClosure[]
  result_readiness: { completion_blockers: ResultIssue[]; report_gaps: ResultIssue[] }
}
