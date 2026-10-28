import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import type { Expertise, HistoricalWork } from '../../api/types'
import { json, page, sessionWith } from '../../test/fixtures'
import { basis, expertise, specialty, testRouter } from '../../test/intakeFixtures'
import { useSessionStore } from '../../stores/session'
import HistoryActivation from './HistoryActivation.vue'
import ExpertisePage from './ExpertisePage.vue'

const history: HistoricalWork = { id: 'h-1', operational: false, complex_known: false, composition_known: false, suspension_history_complete: false, statistics_confirmed: false,
  result_kind: 'expert_conclusion', completed_on: null, return_decided_on: null, issued_on: null, complexity_level: 1, questions: 2, categorical: 2, probable: 0, unresolved: 0, amount: null,
  authority_type: '', authority_name: '', official: '', contact: '', basis_text: '', case_description: '', inventory: '', executor_raw: 'Имя из журнала', unresolved_note: '', unresolved_reason_raw: '', notes: '', delivery: '', current_participants: [], source: { batch_id: 'b-1', row_id: 'r-1', source_row: 4, origin_url: null, source_observed_at: null }, report_gaps: [] }
const imported: Expertise = { ...expertise, origin_kind: 'historical', historical: history, receipt: { ...expertise.receipt, received_at: '2026-10-01', status: 'historical' }, appointment_nature: null, is_commission: null, basis_document: basis, allowed_actions: ['imports.history.activate'] }
const accepted: Expertise = { ...imported, version: 2, historical: { ...history, operational: true, complex_known: true }, appointment_nature: 'primary', is_commission: false, allowed_actions: ['expertise.assign'] }
const fileVersion = { id: 'file-1', number: 1, original_name: 'result.png', content_type: 'image/png', size: 4, sha256: 'abc', created_at: '2026-10-28T00:00:00Z', download_url: '/download/', preview_url: '/preview/' }
type Transport = ConstructorParameters<typeof ApiClient>[0]
async function open(work = imported, transport?: Transport, supported = true) {
  const pinia = sessionWith('expertise.view', 'expertise.register', 'imports.history.activate', 'documents.view', 'documents.upload')
  useSessionStore(pinia).user!.supported_modules = supported ? ['journal_application'] : []
  const router = await testRouter('/expertises/work-1')
  const client = new ApiClient(transport ?? (async () => json(page([specialty]))))
  const wrapper = mount(HistoryActivation, { props: { expertise: work }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } })
  await flushPromises(); return { wrapper, router, pinia }
}
async function fill(wrapper: ReturnType<typeof mount>) {
  await wrapper.get('[data-start-history]').trigger('click'); await flushPromises()
  await wrapper.get('[name="history_nature"]').setValue('primary')
  await wrapper.get('[name="history_commission"]').setValue('no')
  await wrapper.get('[name="history_complex_confirm"]').setValue(true)
  await wrapper.get('[name="history_reason"]').setValue('  Подтверждено по материалам  ')
}
enableAutoUnmount(afterEach); afterEach(() => vi.restoreAllMocks())

describe('explicit history activation', () => {
  it.each(['unsupported', 'no_action'])('does not offer confirmation or fetch data when %s', async condition => {
    const paths: string[] = []
    const { wrapper } = await open(condition === 'no_action' ? { ...imported, allowed_actions: [] } : imported, async input => { paths.push(String(input)); return json(page([])) }, condition !== 'unsupported')
    expect(wrapper.find('[data-start-history]').exists()).toBe(false); expect(paths).toEqual([])
  })

  it('requires explicit composition and posts exact evidence/version without assigning anyone', async () => {
    const writes: { path: string; body: unknown; key: string | null }[] = []
    const { wrapper } = await open(imported, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 't' })
      if (init?.method === 'POST') { writes.push({ path, body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ event: { id: 'event-1' }, expertise: accepted }) }
      return json(page([specialty]))
    })
    await wrapper.get('[data-start-history]').trigger('click'); await flushPromises()
    expect(wrapper.get('[name="history_nature"]').element).toHaveProperty('value', '')
    expect(wrapper.get('[name="history_commission"]').element).toHaveProperty('value', '')
    expect(wrapper.get('[data-confirm-history]').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="history_nature"]').setValue('primary'); await wrapper.get('[name="history_commission"]').setValue('no')
    await wrapper.get('[name="history_complex_confirm"]').setValue(true); await wrapper.get('[name="history_reason"]').setValue('  Подтверждено по материалам  ')
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1); expect(writes[0]!.path).toBe('/api/v1/expertises/work-1/activate-history/'); expect(writes[0]!.key).toBeTruthy()
    expect(writes[0]!.body).toEqual({ expected_version: 1, reason: 'Подтверждено по материалам', basis_document_id: 'document-1', specialty_id: 's-18', appointment_nature: 'primary', is_commission: false, complex_known: true, complex_group_id: null, suspension_history_complete: false, past_suspensions: [], suspended_on: null })
    expect(wrapper.emitted('updated')?.[0]).toEqual([accepted])
  })

  it('keeps a suspended work unconfirmed until an actual pause start is entered', async () => {
    const { wrapper } = await open({ ...imported, state: 'suspended' })
    await fill(wrapper)
    expect(wrapper.get('[data-confirm-history]').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="history_open_pause"]').setValue('2026-10-28')
    expect(wrapper.get('[data-confirm-history]').attributes('disabled')).toBeUndefined()
  })

  it('requires an explicit specialty when it was unknown in the journal', async () => {
    const { wrapper } = await open({ ...imported, specialty: null })
    await fill(wrapper)
    expect(wrapper.get('[data-confirm-history]').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="history_specialty"]').setValue('s-18')
    expect(wrapper.get('[data-confirm-history]').attributes('disabled')).toBeUndefined()
  })

  it('can confirm a permitted existing basis without document-creation permission', async () => {
    const writes: string[] = []
    const { wrapper, pinia } = await open({ ...imported, basis_document: null }, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 't' })
      if (init?.method === 'POST') { writes.push(path); return json({ event: { id: 'event' }, expertise: accepted }) }
      return json(path.includes('/documents/') ? basis : page([specialty]))
    })
    delete useSessionStore(pinia).user!.access['documents.upload']
    await fill(wrapper)
    await wrapper.get('[name="history_basis_id"]').setValue('document-1')
    await wrapper.get('[data-load-history-basis]').trigger('click'); await flushPromises()
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(writes).toEqual(['/api/v1/expertises/work-1/activate-history/'])
  })

  it('requires a saved result file before any closed-work confirmation and reuses it after a lost reply', async () => {
    const paths: string[] = [], attempts: { key: string | null; body: any }[] = []
    const { wrapper } = await open({ ...imported, state: 'completed', historical: { ...history, completed_on: '2026-10-06' } }, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 't' })
      if (init?.method === 'POST') {
        paths.push(path)
        if (path.endsWith('/documents/')) return json({ ...basis, id: 'result-document', kind: 'expert_conclusion' }, 201)
        if (path.endsWith('/versions/')) return json(fileVersion, 201)
        attempts.push({ key: new Headers(init.headers).get('Idempotency-Key'), body: JSON.parse(String(init.body)) })
        if (attempts.length === 1) throw new TypeError('Потерян ответ подтверждения')
        return json({ event: { id: 'activation-event' }, expertise: { ...accepted, state: 'completed' } })
      }
      return json(path.includes('result-options') ? { result_kinds: [], complexity_groups: [], sndz_reasons: [], unresolved_reasons: [], return_reasons: [] } : page([specialty]))
    })
    await fill(wrapper)
    const document = wrapper.get('[data-history-result-document]')
    await document.get('[name="document_title"]').setValue('Фактическое заключение')
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(attempts).toEqual([]); expect(paths).toEqual([])
    Object.defineProperty(document.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'result.png')] })
    await document.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(attempts).toHaveLength(2); expect(attempts[1]).toEqual(attempts[0])
    expect(attempts[0]!.body.result.document_id).toBe('result-document')
    expect(attempts[0]!.body.result.completed_on).toBe('2026-10-06')
    expect(paths.filter(path => path.endsWith('/documents/'))).toHaveLength(1)
    expect(paths.filter(path => path.endsWith('/versions/'))).toHaveLength(1)
  })

  it('retains a rejected form and adopts a newer work version only explicitly', async () => {
    const bodies: { body: any; key: string | null }[] = []
    const { wrapper } = await open(imported, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 't' })
      if (init?.method === 'POST') { bodies.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ code: 'version_conflict', message: 'Обновите карточку', field_errors: {} }, 409) }
      return json(page([specialty]))
    })
    await fill(wrapper); await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    await wrapper.setProps({ expertise: { ...imported, version: 2 } })
    expect(wrapper.get('[name="history_reason"]').element).toHaveProperty('value', '  Подтверждено по материалам  ')
    await wrapper.get('[data-adopt-history-version]').trigger('click')
    await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(bodies[0]!.body.expected_version).toBe(1); expect(bodies[1]!.body.expected_version).toBe(2)
    expect(bodies[0]!.key).not.toBe(bodies[1]!.key)
  })

  it('guards unsaved evidence/composition when leaving is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await open(); await fill(wrapper)
    await router.push('/expertises/work-2')
    expect(router.currentRoute.value.params.id).toBe('work-1')
    expect(wrapper.get('[name="history_reason"]').element).toHaveProperty('value', '  Подтверждено по материалам  ')
  })

  it('integrates confirmation into the actual work card and enables only the refreshed server actions', async () => {
    const pinia = sessionWith('expertise.view', 'expertise.register', 'expertise.assign', 'imports.history.activate', 'documents.view', 'documents.upload')
    useSessionStore(pinia).user!.supported_modules = ['journal_application']
    const router = await testRouter('/expertises/work-1')
    const client = new ApiClient(async (input, init) => String(input).endsWith('/csrf/') ? json({ csrf_token: 't' }) : init?.method === 'POST' ? json({ event: { id: 'event' }, expertise: accepted }) : json(imported))
    const wrapper = mount(ExpertisePage, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-start-assignment]').exists()).toBe(false)
    await fill(wrapper); await wrapper.get('[data-history-form]').trigger('submit'); await flushPromises()
    expect(wrapper.find('[data-history-form]').exists()).toBe(false)
    expect(wrapper.find('[data-start-assignment]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Версия работы 2')
    expect(wrapper.text()).toContain('подтверждена для нового учёта')
  })
})
