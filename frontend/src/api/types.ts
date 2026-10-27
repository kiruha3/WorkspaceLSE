export type Scope = 'own' | 'departments' | 'institution'
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface AccessGrant {
  scope: Scope; scope_limit: Scope; department_ids: string[]
  role_id: string; role_name: string; assignment_id: string
}
export type Access = Record<string, AccessGrant[]>
export interface CurrentUser { id: string; username: string; employee: { id: string; full_name: string } | null; access: Access }
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
