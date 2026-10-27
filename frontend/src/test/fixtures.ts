import { createPinia, setActivePinia } from 'pinia'
import { useSessionStore } from '../stores/session'
import type { CurrentUser, Employee, Role } from '../api/types'

export const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
export const page = <T>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
export function sessionWith(...codes: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const session = useSessionStore()
  session.user = {
    id: 'user-1', username: 'tester', employee: { id: 'employee-1', full_name: 'Тестовый сотрудник' },
    access: Object.fromEntries(codes.map(code => [code, [{ scope: 'institution', scope_limit: 'institution', department_ids: [], role_id: 'r-1', role_name: 'Роль', assignment_id: 'a-1' }]])),
  } as CurrentUser
  session.ready = true
  return pinia
}
export const role: Role = {
  id: 'role-1', name: 'Руководитель и эксперт', description: 'Совмещение в одной учётной записи',
  is_active: true, version: 4, assignment_count: 2,
  permissions: [{ permission_code: 'employees.view', scope: 'departments' }],
}
export const employee: Employee = {
  id: 'employee-1', full_name: 'Тестовый сотрудник', is_active: true, version: 2,
  org_assignments: [{ id: 'org-1', department: { id: 'd-4', code: '4', name: 'Отдел 4' }, position: { id: 'p-1', code: 'expert', name: 'Эксперт' }, valid_from: '2026-01-01', valid_to: null, version: 1, reason: 'Кадровый приказ' }],
  specialties: [
    { id: 'es-1', specialty: { id: 's-18', code: '18.1', name: 'Исследование записи' }, status: 'qualified', training_started_at: null, qualified_at: '2025-04-03', valid_until: null, basis: 'Подтверждённое основание', mentor_id: null, version: 2 },
    { id: 'es-2', specialty: { id: 's-13', code: '13.1', name: 'Исследование машин' }, status: 'training', training_started_at: '2026-10-01', qualified_at: null, valid_until: null, basis: 'План обучения', mentor_id: null, version: 1 },
  ],
}
