import { createMemoryHistory, createRouter } from 'vue-router'
import type { BasisDocument, Expertise, Receipt, Reference } from '../api/types'
export const department: Reference = { id: 'd-4', code: '4', name: 'Отдел 4', is_active: true, version: 1 }
export const specialty: Reference = { id: 's-18', code: '18.1', name: 'Исследование записи', is_active: true, version: 1 }
export const basis: BasisDocument = { id: 'document-1', kind: 'resolution', title: 'Постановление суда', source_kind: 'paper_original', department_id: 'd-4', version: 1, versions: [] }
export const receipt: Receipt = { id: 'receipt-1', received_at: '2026-10-28', sender_name: 'Районный суд', material: { id: 'material-1', title: 'Материалы дела' }, basis_document: basis, department_id: 'd-4', status: 'accepted', version: 2 }
export const expertise: Expertise = {
  origin_kind: 'native', historical: null,
  id: 'work-1', registration_number: '151/4-1-26', historical_number: '', sequence: 151, year: 2026, category_code: '1', department, specialty,
  receipt: { id: receipt.id, received_at: receipt.received_at, status: receipt.status }, material: receipt.material, appointment_nature: 'primary', is_commission: false, complex_group: null,
  state: 'in_progress', version: 1, current_assignments: [], assignment_history: [], allowed_actions: ['expertise.assign'], basis_document: basis,
  production: { as_of: '2026-10-28', counted_through: '2026-10-28', method: 'calendar_inclusive_pause_half_open_v1', calendar_days: 1, paused_days: 0, active_calendar_days: 1, initial_due_on: null, agreed_due_on: null, current_due_on: null, last_requested_due_on: null, overdue_calendar_days: null }, suspensions: [], deadline_events: [],
  result: null, result_history: [], closure: null, closure_history: [], result_readiness: { completion_blockers: [], report_gaps: [] },
}
export async function testRouter(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: ['/intake', '/receipts/:id', '/expertises', '/expertises/:id'].map(path => ({ path, component: { template: '<div />' } })) })
  await router.push(path)
  await router.isReady()
  return router
}
