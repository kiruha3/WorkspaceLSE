import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import type { CaseDetails, Expertise, HistoricalWork } from '../../api/types'
import { json, page, sessionWith } from '../../test/fixtures'
import { expertise, testRouter } from '../../test/intakeFixtures'
import { useSessionStore } from '../../stores/session'
import ExpertisePage from './ExpertisePage.vue'

enableAutoUnmount(afterEach)
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = '' })

const history: HistoricalWork = {
  id: 'history-layout', operational: false, complex_known: false, composition_known: false,
  suspension_history_complete: false, statistics_confirmed: false,
  result_kind: 'expert_conclusion', completed_on: '2026-03-13', return_decided_on: null, issued_on: '2026-03-23',
  complexity_level: 1, questions: 1, categorical: 1, probable: 0, unresolved: null, amount: null,
  authority_type: 'СК', authority_name: 'Орган из журнала', official: '', contact: '', basis_text: '',
  case_description: 'Исходное описание', inventory: 'Исходная опись', executor_raw: 'Подлипаева Т.И.',
  unresolved_note: '', unresolved_reason_raw: '', notes: '', delivery: '', current_participants: [{ id: 'old-expert', full_name: 'Подлипаева Т.И.' }],
  source: { batch_id: 'batch', row_id: 'row', source_row: 168, origin_url: null, source_observed_at: null }, report_gaps: [],
}
const historical: Expertise = { ...expertise, origin_kind: 'historical', historical: history, state: 'completed', allowed_actions: [], basis_document: null }
const details: CaseDetails = {
  id: null, source: 'new', can_edit: true, edit_permission: 'expertise.work.update',
  authority_type: null, authority_type_raw: '', authority_name: 'Начальный орган', official: '', contact: '',
  case_number: '', case_description: '', basis_text: '', inventory: '', questions_text: '',
  decree3214: null, decree_document_id: null, decree_document: null, decree_basis: '', revisions: [],
}
async function open(current: Expertise = historical, modules: string[] = [], codes: string[] = ['expertise.view']) {
  const router = await testRouter('/expertises/work-1?return=%2Fexpertises%3Fpage%3D2')
  for (const path of ['/expertises/:id/documents', '/letters']) router.addRoute({ path, component: { template: '<div />' } })
  const pinia = sessionWith(...codes), session = useSessionStore(pinia)
  session.user!.supported_modules = modules
  let work = current
  const writes: string[] = []
  const wrapper = mount(ExpertisePage, { attachTo: document.body, global: { plugins: [pinia, router], provide: {
    [apiKey as symbol]: new ApiClient(async (input, init) => {
      const path = String(input)
      if (init?.method === 'POST') { writes.push(path); return json({ expertise: work }) }
      if (path.endsWith('/case-details/')) return json({ authority_types: [], initial_authority_type_id: null, retained_authority_type_ids: [] })
      if (path.includes('/letters/')) return json(page([]))
      if (path.endsWith('/issue-status/')) return json({ status: 'unavailable', package: null })
      return json(work)
    }),
  } } })
  await flushPromises()
  return { wrapper, router, session, writes, setWork: (next: Expertise) => { work = next } }
}

// Catches loss of the approved first screen and accidental duplicate case headings.
it('opens the compact overview with one identity and explicit historical sources', async () => {
  const { wrapper, writes } = await open()
  expect(wrapper.findAll('h1')).toHaveLength(1)
  expect(wrapper.get('[data-card-tab="overview"]').attributes('aria-selected')).toBe('true')
  expect(wrapper.get('[data-card-panel="overview"]').isVisible()).toBe(true)
  expect(wrapper.get('[data-card-panel="production"]').isVisible()).toBe(false)
  const summary = wrapper.get('[data-card-summary]')
  expect(summary.text()).toContain('Исполнители в источнике')
  expect(summary.text()).toContain('Подлипаева Т.И.')
  expect(summary.text()).toContain('Историческая дата окончания')
  expect(summary.text()).toContain('13.03.2026')
  expect(summary.text()).toContain('Фактическая выдача в журнале')
  expect(summary.text()).toContain('23.03.2026')
  expect(wrapper.get('[data-current-assignments]').text()).not.toContain('Подлипаева')
  expect(writes).toEqual([])
})

it('retains genuine zero and unknown separately in overview statistics', async () => {
  const { wrapper } = await open()
  expect(wrapper.get('[data-overview-fact="probable"]').text()).toBe('0')
  expect(wrapper.get('[data-overview-fact="unresolved"]').text()).toBe('Неизвестно')
  expect(wrapper.get('[data-overview-fact="amount"]').text()).toBe('Неизвестно')
})

it('keeps the source summary visible while reading another section', async () => {
  const { wrapper } = await open()
  await wrapper.get('[data-card-tab="production"]').trigger('click')
  expect(wrapper.get('[data-card-summary]').isVisible()).toBe(true)
  expect(wrapper.get('[data-card-summary]').text()).toContain('Подлипаева Т.И.')
})

it('does not present a native result draft date as a confirmed ending or issue', async () => {
  const { wrapper } = await open({ ...expertise, allowed_actions: [], result: {
    id: 'draft', number: 1, kind: 'expert_conclusion', completed_on: '2026-10-28', document: null,
    complexity_level: 1, questions: 0, categorical: 0, probable: 0, unresolved: 0, statistics_complete: true,
    sndz_reason: null, sndz_comment: '', unresolved_allocations: [], allocations_complete: false, note: '', actor: { id: 'author', full_name: 'Автор черновика' }, created_at: '2026-10-28T00:00:00Z', reason: '',
  } })
  expect(wrapper.get('[data-card-summary]').text()).not.toContain('Дата окончания')
  expect(wrapper.get('[data-card-summary]').text()).not.toContain('Выдача')
  expect(wrapper.get('[data-overview-result]').text()).toContain('Черновик')
})

it.each([
  { kind: 'without_execution' as const, resultId: null, draft: true },
  { kind: 'completed' as const, resultId: 'older-result', draft: true },
  { kind: 'completed' as const, resultId: 'latest-result', draft: false },
])('marks the current result accepted only when a completed closure references it: $kind/$resultId', async ({ kind, resultId, draft }) => {
  const actor = { id: 'author', full_name: 'Автор результата' }
  const { wrapper } = await open({ ...expertise, allowed_actions: [], state: kind, closure: {
    id: 'closure', number: 1, kind, ended_on: '2026-10-28', document: null, result_id: resultId,
    return_reason: null, comment: '', actor, created_at: '2026-10-28T00:00:00Z', reason: '',
  }, result: {
    id: 'latest-result', number: 1, kind: 'expert_conclusion', completed_on: '2026-10-28', document: null,
    complexity_level: 1, questions: 1, categorical: 1, probable: 0, unresolved: 0, statistics_complete: true,
    sndz_reason: null, sndz_comment: '', unresolved_allocations: [], allocations_complete: false, note: '', actor,
    created_at: '2026-10-28T00:00:00Z', reason: '',
  } })
  expect(wrapper.get('[data-overview-result]').text().includes('Черновик')).toBe(draft)
})

it('keeps an edited real form mounted and unsaved when switching tabs', async () => {
  const confirm = vi.spyOn(window, 'confirm')
  const { wrapper, writes } = await open({ ...expertise, case_details: details, allowed_actions: [] })
  await wrapper.get('[data-card-tab="case"]').trigger('click')
  await wrapper.get('[data-case-edit]').trigger('click'); await flushPromises()
  await wrapper.get('[name="case_authority_name"]').setValue('Несохранённый орган')
  await wrapper.get('[name="case_reason"]').setValue('Несохранённое основание')
  await wrapper.get('[data-card-tab="production"]').trigger('click')
  expect(wrapper.get('[data-case-form]').isVisible()).toBe(false)
  expect(wrapper.get('[data-card-panel="production"]').isVisible()).toBe(true)
  await wrapper.get('[data-card-tab="case"]').trigger('click')
  expect(wrapper.get('[data-case-form]').isVisible()).toBe(true)
  expect(wrapper.get('[name="case_authority_name"]').element).toHaveProperty('value', 'Несохранённый орган')
  expect(wrapper.get('[name="case_reason"]').element).toHaveProperty('value', 'Несохранённое основание')
  expect(writes).toEqual([]); expect(confirm).not.toHaveBeenCalled()
})

it('keeps the dirty route guard active even for a form hidden in another tab', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(false)
  const { wrapper, router } = await open({ ...expertise, case_details: details, allowed_actions: [] })
  await wrapper.get('[data-card-tab="case"]').trigger('click')
  await wrapper.get('[data-case-edit]').trigger('click'); await flushPromises()
  await wrapper.get('[name="case_reason"]').setValue('Не потерять')
  await wrapper.get('[data-card-tab="overview"]').trigger('click')
  await router.push('/expertises/work-2'); await flushPromises()
  expect(router.currentRoute.value.params.id).toBe('work-1')
  expect(wrapper.get('[name="case_reason"]').element).toHaveProperty('value', 'Не потерять')
})

it('resets to overview and drops source facts after changing work identity', async () => {
  const { wrapper, router, setWork } = await open()
  await wrapper.get('[data-card-tab="history"]').trigger('click')
  expect(wrapper.get('[data-historical-facts]').isVisible()).toBe(true)
  setWork({ ...expertise, id: 'work-2' })
  await router.push('/expertises/work-2'); await flushPromises()
  expect(wrapper.get('[data-card-tab="overview"]').attributes('aria-selected')).toBe('true')
  expect(wrapper.text()).not.toContain('Подлипаева')
  expect(wrapper.find('[data-card-tab="history"]').exists()).toBe(false)
})

it('exposes only previously permitted sections and keeps registry/archives navigation', async () => {
  const { wrapper } = await open(historical, ['work_documents'], ['expertise.view', 'expertise.assign', 'documents.view'])
  expect(wrapper.find('[data-card-tab="letters"]').exists()).toBe(false)
  expect(wrapper.find('[data-card-tab="issuance"]').exists()).toBe(false)
  await wrapper.get('[data-card-tab="assignments"]').trigger('click')
  expect(wrapper.find('[data-start-assignment]').exists()).toBe(false)
  expect(wrapper.get('[data-back-to-expertises]').attributes('href')).toBe('/expertises?page=2')
  expect(wrapper.get('[data-work-document-archive]').attributes('href')).toContain('/expertises/work-1/documents?return=')
})

it('returns to overview if access to the selected correspondence section is revoked', async () => {
  const { wrapper, session } = await open(historical, ['correspondence'], ['expertise.view', 'letters.view'])
  await wrapper.get('[data-card-tab="letters"]').trigger('click')
  expect(wrapper.get('[data-card-panel="letters"]').isVisible()).toBe(true)
  session.user!.access = { 'expertise.view': session.user!.access['expertise.view']! }
  await flushPromises()
  expect(wrapper.find('[data-card-tab="letters"]').exists()).toBe(false)
  expect(wrapper.get('[data-card-tab="overview"]').attributes('aria-selected')).toBe('true')
})

it('moves focus and selected panel with arrows, Home and End without business writes', async () => {
  const { wrapper, writes } = await open()
  const first = wrapper.get('[data-card-tab="overview"]')
  await first.trigger('keydown', { key: 'ArrowRight' })
  const next = wrapper.get('[data-card-tab="case"]')
  expect(next.attributes('aria-selected')).toBe('true')
  expect(document.activeElement).toBe(next.element)
  await next.trigger('keydown', { key: 'End' })
  expect(wrapper.get('[data-card-tab="history"]').attributes('aria-selected')).toBe('true')
  await wrapper.get('[data-card-tab="history"]').trigger('keydown', { key: 'Home' })
  expect(first.attributes('aria-selected')).toBe('true')
  expect(wrapper.findAll('[role="tab"][tabindex="0"]')).toHaveLength(1)
  expect(writes).toEqual([])
})
