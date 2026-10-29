import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import { basis, expertise, testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'

afterEach(() => vi.restoreAllMocks())
const reference = (id: string, code = id, active = true) => ({ id, code, name: `Причина ${id}`, is_active: active, version: 1 })
const options = { result_kinds: [{ code: 'expert_conclusion', name: 'Заключение эксперта' }, { code: 'sndz', name: 'СНДЗ' }], complexity_groups: [{ code: 'above_3', name: 'Выше 3' }], sndz_reasons: [reference('sndz'), reference('inactive', 'old', false)], unresolved_reasons: [reference('unresolved'), reference('other', 'other')], return_reasons: [reference('return')] }
const file = { id: 'file', number: 1, original_name: 'result.pdf', content_type: 'application/pdf', size: 8, sha256: 'abc', created_at: '2026-10-28T00:00:00Z', download_url: '/result/download/', preview_url: '/result/preview/' }
const document = { ...basis, id: 'result-doc', kind: 'expert_conclusion', title: 'Заключение', versions: [file] }
const result = { id: 'result-1', number: 1, kind: 'expert_conclusion', completed_on: '2026-10-28', document, complexity_level: 5, questions: 4, categorical: 2, probable: null, unresolved: 0, statistics_complete: false, sndz_reason: null, sndz_comment: '', unresolved_allocations: [], allocations_complete: false, note: 'Исследовано', actor: { id: 'actor', full_name: 'Эксперт Иванов' }, created_at: '2026-10-28T00:00:00Z', reason: 'Первое сохранение' }
const work = { ...expertise, result: null, result_history: [], closure: null, closure_history: [], result_readiness: { completion_blockers: [{ code: 'result_missing', field: 'result', message: 'Сохраните результат' }], report_gaps: [{ code: 'statistics_unknown', field: 'questions', message: 'Статистика неизвестна' }] }, allowed_actions: ['expertise.result.draft', 'expertise.complete', 'expertise.return_without_execution'] }
const withResult = { ...work, result, result_history: [result], result_readiness: { completion_blockers: [], report_gaps: work.result_readiness.report_gaps } }
type Write = { path: string; body: Record<string, unknown>; raw: string; key: string | null }
async function open(current: unknown = work, respond?: (write: Write, count: number) => Response | Promise<Response>, evidence?: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  const writes: Write[] = []; let value = current
  const router = await testRouter('/expertises/work-1')
  const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'documents.upload', 'expertise.closed.correct'), router], provide: { [apiKey as symbol]: new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'csrf' })
    if (path.endsWith('/result-options/')) return json(options)
    if (path.includes('/documents/') && evidence) return evidence(path, init)
    if (init?.method === 'POST') { const write = { path, body: JSON.parse(String(init.body)), raw: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') }; writes.push(write); return respond ? respond(write, writes.length) : json({ event: { id: 'event' }, expertise: { ...withResult, version: 2 } }) }
    return json(value)
  }) } } })
  await flushPromises()
  return { wrapper, writes, router, set: (next: unknown) => { value = next }, refresh: async () => { await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises() } }
}
async function draft(wrapper: Awaited<ReturnType<typeof open>>['wrapper']) { await wrapper.get('[data-result-draft]').trigger('click'); await flushPromises(); await wrapper.get('[name="result_reason"]').setValue('  Достоверные сведения  ') }

describe('result and closure workflow', () => {
  it('shows missing documents as reminders without blocking completion', async () => {
    const { wrapper, writes } = await open({ ...withResult, result: { ...result, document: null }, result_readiness: { completion_blockers: [], report_gaps: [], document_gaps: [{ code: 'file_missing', field: 'document_id', message: 'Не прикреплён итоговый документ.' }] } })
    expect(wrapper.get('[data-document-gaps]').text()).toContain('Не прикреплён итоговый документ')
    expect(wrapper.get('[data-result-complete]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-result-complete]').trigger('click'); await wrapper.get('[name="result_reason"]').setValue('Завершено, файл добавим позже')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/complete/')
    wrapper.unmount()
  })
  it('records a return without an attached decision document', async () => {
    const { wrapper, writes } = await open()
    await wrapper.get('[data-result-return]').trigger('click'); await flushPromises()
    await wrapper.get('[name="result_reason"]').setValue('Возврат подтверждён'); await wrapper.get('[name="decided_on"]').setValue('2026-10-28')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body.document_id).toBeNull()
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/return-without-execution/')
    wrapper.unmount()
  })
  it('corrects result details without requiring a file', async () => {
    const value = { ...withResult, result: { ...result, document: null }, state: 'completed', closure: { id: 'closure', kind: 'completed', document: null }, allowed_actions: ['expertise.closed.correct'] }
    const { wrapper, writes } = await open(value)
    await wrapper.get('[data-result-correct]').trigger('click'); await flushPromises()
    await wrapper.get('[name="result_reason"]').setValue('Уточнение без файла'); await wrapper.get('[name="probable"]').setValue('2')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body.result).toMatchObject({ document_id: null, probable: 2 })
    wrapper.unmount()
  })
  it('gates actions by the card and distinguishes completion blockers from reporting gaps', async () => {
    const { wrapper } = await open({ ...work, allowed_actions: [] })
    expect(wrapper.get('[data-result-panel]').text()).toContain('Сохраните результат')
    expect(wrapper.get('[data-report-gaps]').text()).toContain('Статистика неизвестна')
    expect(wrapper.find('[data-result-draft]').exists()).toBe(false)
    expect(wrapper.find('[data-result-complete]').exists()).toBe(false)
    expect(wrapper.find('[data-result-return]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Выдать заключение')
    wrapper.unmount()
  })
  it('saves a partial draft with explicit nulls and zero as different values', async () => {
    const { wrapper, writes } = await open()
    await draft(wrapper)
    await wrapper.get('[name="questions"]').setValue('4'); await wrapper.get('[name="categorical"]').setValue('2'); await wrapper.get('[name="unresolved"]').setValue('0'); await wrapper.get('[name="complexity_level"]').setValue('5')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/result/')
    expect(writes[0]?.body).toEqual({ expected_version: 1, reason: 'Достоверные сведения', kind: null, completed_on: null, document_id: null, complexity_level: 5, questions: 4, categorical: 2, probable: null, unresolved: 0, statistics_complete: false, sndz_reason_id: null, sndz_comment: '', unresolved_allocations: [], allocations_complete: false, note: '' })
    expect(writes[0]?.key).toBeTruthy()
    expect(wrapper.find('[data-result-form]').exists()).toBe(false)
    expect(wrapper.get('[data-current-result]').text()).toContain('Неизвестно')
    wrapper.unmount()
  })
  it('keeps whole SNDZ reasons separate from unresolved allocations and their catalogs', async () => {
    const { wrapper, writes } = await open()
    await draft(wrapper); await wrapper.get('[name="result_kind"]').setValue('sndz')
    expect(wrapper.find('[name="sndz_reason_id"] [value="sndz"]').exists()).toBe(true)
    expect(wrapper.find('[name="sndz_reason_id"] [value="unresolved"]').exists()).toBe(false)
    expect(wrapper.find('[name="sndz_reason_id"] [value="inactive"]').exists()).toBe(false)
    await wrapper.get('[name="sndz_reason_id"]').setValue('sndz')
    await wrapper.get('[name="unresolved"]').setValue('2')
    await wrapper.get('[data-add-allocation]').trigger('click')
    await wrapper.get('[name="allocation_reason_0"]').setValue('unresolved'); await wrapper.get('[name="allocation_count_0"]').setValue('2')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body.sndz_reason_id).toBe('sndz')
    expect(writes[0]?.body.unresolved_allocations).toEqual([{ reason_id: 'unresolved', count: 2, comment: '', document_id: null }])
    wrapper.unmount()
  })
  it('validates known statistical totals and other allocation explanations without inventing unknown values', async () => {
    const { wrapper, writes } = await open()
    await draft(wrapper); await wrapper.get('[name="questions"]').setValue('4'); await wrapper.get('[name="categorical"]').setValue('5')
    await wrapper.get('[data-result-form]').trigger('submit'); expect(writes).toHaveLength(0)
    await wrapper.get('[name="categorical"]').setValue('2'); await wrapper.get('[name="statistics_complete"]').setValue(true)
    await wrapper.get('[data-result-form]').trigger('submit'); expect(writes).toHaveLength(0)
    await wrapper.get('[name="statistics_complete"]').setValue(false); await wrapper.get('[name="unresolved"]').setValue('2'); await wrapper.get('[data-add-allocation]').trigger('click')
    await wrapper.get('[name="allocation_reason_0"]').setValue('other'); await wrapper.get('[name="allocation_count_0"]').setValue('2')
    await wrapper.get('[data-result-form]').trigger('submit'); expect(writes).toHaveLength(0)
    await wrapper.get('[name="allocation_comment_0"]').setValue('Причина описана')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises(); expect(writes).toHaveLength(1)
    wrapper.unmount()
  })
  it('completes only the persisted latest result despite optional reporting gaps', async () => {
    const { wrapper, writes } = await open(withResult)
    await wrapper.get('[data-result-complete]').trigger('click'); await wrapper.get('[name="result_reason"]').setValue('Итог подтверждён')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/complete/')
    expect(writes[0]?.body).toEqual({ expected_version: 1, reason: 'Итог подтверждён', result_id: 'result-1' })
    wrapper.unmount()
    const blocked = await open({ ...withResult, result: { ...result, document: { ...document, versions: [] } }, result_readiness: { completion_blockers: [{ code: 'file_required', field: 'document', message: 'Сохраните файл' }], report_gaps: [] } })
    expect(blocked.wrapper.get('[data-result-complete]').attributes('disabled')).toBeDefined()
    blocked.wrapper.unmount()
  })
  it('returns with its own reason catalog and does not create an issue date', async () => {
    const { wrapper, writes } = await open({ ...work, closure_history: [{ id: 'old', number: 1, kind: 'without_execution', ended_on: '2026-10-28', document: { ...document, id: 'return-doc', kind: 'return_decision' }, result_id: null, return_reason: null, comment: '', actor: result.actor, created_at: result.created_at, reason: 'Решение' }] })
    await wrapper.get('[data-result-return]').trigger('click'); await flushPromises()
    await wrapper.get('[name="result_reason"]').setValue('Решение принято'); await wrapper.get('[name="decided_on"]').setValue('2026-10-28')
    await wrapper.get('[name="result_document"]').setValue('return-doc'); await wrapper.get('[name="return_reason_id"]').setValue('return')
    expect(wrapper.find('[name="return_reason_id"] [value="sndz"]').exists()).toBe(false)
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body).toEqual({ expected_version: 1, reason: 'Решение принято', decided_on: '2026-10-28', document_id: 'return-doc', return_reason_id: 'return', comment: '' })
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/return-without-execution/')
    wrapper.unmount()
  })
  it('corrects closed results with a nested payload and renders immutable typed histories', async () => {
    const closure = { id: 'closure-1', number: 1, kind: 'completed', ended_on: '2026-10-28', document, result_id: 'result-1', return_reason: null, comment: '', actor: result.actor, created_at: result.created_at, reason: 'Подтверждено' }
    const { wrapper, writes } = await open({ ...withResult, state: 'completed', closure, closure_history: [closure], allowed_actions: ['expertise.closed.correct'] })
    expect(wrapper.get('[data-result-history]').text()).toContain('Эксперт Иванов')
    expect(wrapper.get('[data-closure-history]').text()).toContain('Подтверждено')
    expect(wrapper.find('iframe').exists()).toBe(true)
    expect(wrapper.find('[data-result-draft]').exists()).toBe(false)
    await wrapper.get('[data-result-correct]').trigger('click'); await flushPromises(); await wrapper.get('[name="result_reason"]').setValue('Уточнение статистики'); await wrapper.get('[name="probable"]').setValue('2')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/correct/')
    expect(writes[0]?.body.correction_kind).toBe('result')
    expect(writes[0]?.body.result).toMatchObject({ questions: 4, probable: 2, document_id: 'result-doc' })
    expect(writes[0]?.body.result).not.toHaveProperty('expected_version')
    wrapper.unmount()
  })
  it('retains a normalized lost-response body and key after refresh changes permissions and dates', async () => {
    const { wrapper, writes, set, refresh } = await open(work, (_write, count) => { if (count === 1) throw new TypeError('Lost'); return json({ event: { id: 'same' }, expertise: { ...withResult, version: 2 } }) })
    await draft(wrapper); await wrapper.get('[name="questions"]').setValue('0'); await wrapper.get('[name="completed_on"]').setValue('2026-10-28'); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    set({ ...work, version: 2, allowed_actions: [], receipt: { ...work.receipt, received_at: '2026-10-29' } }); await refresh()
    await wrapper.get('[name="result_reason"]').setValue('Достоверные сведения   ')
    expect(wrapper.get('[data-result-submit]').attributes('formnovalidate')).toBeDefined()
    expect(wrapper.get('[name="completed_on"]').attributes('min')).toBe('2026-10-29')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]?.raw).toBe(writes[0]?.raw); expect(writes[1]?.key).toBe(writes[0]?.key)
    wrapper.unmount()
  })
  it('retains a forbidden draft and uses the new version only after explicit conflict acceptance', async () => {
    const { wrapper, writes, set, refresh } = await open(work, (_write, count) => json({ code: count === 1 ? 'permission_denied' : 'version_conflict', message: 'Сохраните черновик', field_errors: {} }, count === 1 ? 403 : 409))
    await draft(wrapper); await wrapper.get('[name="questions"]').setValue('0'); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(wrapper.get('[name="questions"]').element).toHaveProperty('value', '0')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises(); expect(writes[1]?.key).toBe(writes[0]?.key)
    set({ ...work, version: 3 }); await refresh()
    await wrapper.get('[data-result-accept-version]').trigger('click'); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[2]?.body.expected_version).toBe(3); expect(writes[2]?.key).not.toBe(writes[0]?.key)
    wrapper.unmount()
  })
  it('protects an edited result when navigation is refused', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await open(); await draft(wrapper); await wrapper.get('[name="questions"]').setValue('3')
    await router.push('/expertises'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    expect(wrapper.get('[name="questions"]').element).toHaveProperty('value', '3')
    wrapper.unmount()
  })
  it('requires a correction date but permits a missing document', async () => {
    const closure = { id: 'closed', number: 1, kind: 'completed', ended_on: '2026-10-28', document, result_id: result.id, return_reason: null, comment: '', actor: result.actor, created_at: result.created_at, reason: 'Готово' }
    const { wrapper, writes } = await open({ ...withResult, state: 'completed', closure, closure_history: [closure], allowed_actions: ['expertise.closed.correct'] })
    await wrapper.get('[data-result-correct]').trigger('click'); await flushPromises(); await wrapper.get('[name="result_reason"]').setValue('Исправление')
    await wrapper.get('[name="completed_on"]').setValue(''); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(0)
    await wrapper.get('[name="completed_on"]').setValue('2026-10-28'); await wrapper.get('[name="result_document"]').setValue(''); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1)
    expect(writes[0]?.body.result).toMatchObject({ document_id: null, completed_on: '2026-10-28' })
    wrapper.unmount()
  })
  it('does not carry an SNDZ reason into another result kind', async () => {
    const { wrapper, writes } = await open()
    await draft(wrapper); await wrapper.get('[name="result_kind"]').setValue('sndz'); await wrapper.get('[name="sndz_reason_id"]').setValue('sndz'); await wrapper.get('[name="sndz_comment"]').setValue('Пояснение СНДЗ')
    await wrapper.get('[name="result_kind"]').setValue('expert_conclusion'); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body.sndz_reason_id).toBeNull(); expect(writes[0]?.body.sndz_comment).toBe('')
    wrapper.unmount()
  })
  it('keeps a prepared file and the numeric draft through upload loss and a work conflict', async () => {
    let created = 0
    const uploads: { key: string | null; version: FormDataEntryValue | null; file: FormDataEntryValue | null }[] = []
    const { wrapper, writes, set, refresh } = await open(work, () => json({ code: 'version_conflict', message: 'Обновите карточку', field_errors: {} }, 409), (path, init) => {
      if (path.endsWith('/documents/')) { created++; expect(JSON.parse(String(init?.body))).toEqual({ kind: 'expert_conclusion', title: 'Итоговый файл', source_kind: 'uploaded_copy', department_id: 'd-4' }); return json({ ...document, versions: [] }, 201) }
      uploads.push({ key: new Headers(init?.headers).get('Idempotency-Key'), version: (init?.body as FormData).get('expected_version'), file: (init?.body as FormData).get('file') })
      if (uploads.length === 1) throw new TypeError('Upload lost')
      return json(file, 201)
    })
    await draft(wrapper); await wrapper.get('[name="result_kind"]').setValue('expert_conclusion'); await wrapper.get('[name="questions"]').setValue('0'); await wrapper.get('[name="result_document"]').setValue('new')
    await wrapper.get('[name="document_title"]').setValue('Итоговый файл'); await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
    const scan = new File(['evidence'], 'result.pdf')
    Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [scan] }); await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises(); expect(writes).toHaveLength(0)
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises(); expect(writes[0]?.body.document_id).toBe('result-doc')
    expect(created).toBe(1); expect(uploads).toHaveLength(2); expect(uploads[1]).toEqual(uploads[0])
    set({ ...work, version: 2 }); await refresh(); await wrapper.get('[name="document_title"]').setValue('  Итоговый файл  '); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(created).toBe(1); expect(uploads).toHaveLength(2); expect(writes[1]?.raw).toBe(writes[0]?.raw); expect(writes[1]?.key).toBe(writes[0]?.key)
    expect(wrapper.get('[name="questions"]').element).toHaveProperty('value', '0'); expect(wrapper.text()).toContain('Файл сохранён')
    wrapper.unmount()
  })
  it('retains inactive historical selections while excluding unrelated inactive choices', async () => {
    const saved = { ...result, kind: 'sndz', document: { ...document, kind: 'sndz' }, sndz_reason: reference('inactive', 'old', false) }
    const { wrapper, writes } = await open({ ...withResult, result: saved, result_history: [saved] })
    await draft(wrapper)
    expect(wrapper.get('[name="sndz_reason_id"]').element).toHaveProperty('value', 'inactive')
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body.sndz_reason_id).toBe('inactive')
    wrapper.unmount()
  })
  it('corrects a return through the return command shape and preserves unknown reasons', async () => {
    const closure = { id: 'return', number: 1, kind: 'without_execution', ended_on: '2026-10-28', document: { ...document, id: 'return-doc', kind: 'return_decision' }, result_id: null, return_reason: null, comment: 'Причина уточняется', actor: result.actor, created_at: result.created_at, reason: 'Решение' }
    const { wrapper, writes } = await open({ ...work, state: 'without_execution', closure, closure_history: [closure], allowed_actions: ['expertise.closed.correct'] })
    await wrapper.get('[data-result-correct]').trigger('click'); await flushPromises(); await wrapper.get('[name="result_reason"]').setValue('Уточнение пояснения'); await wrapper.get('[name="return_comment"]').setValue('Дополнено')
    expect(wrapper.find('[name="result_kind"]').exists()).toBe(false)
    await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.body).toEqual({ expected_version: 1, reason: 'Уточнение пояснения', correction_kind: 'return', decided_on: '2026-10-28', document_id: 'return-doc', return_reason_id: null, comment: 'Дополнено' })
    wrapper.unmount()
  })
  it('cancels an older detail GET when result saving returns a fresh work', async () => {
    let reads = 0, resolveOld!: (value: Response) => void
    const old = new Promise<Response>(resolve => { resolveOld = resolve })
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'csrf' })
      if (path.endsWith('/result-options/')) return json(options)
      if (init?.method === 'POST') return json({ event: { id: 'result' }, expertise: { ...withResult, version: 2 } })
      return ++reads === 1 ? json(work) : old
    }) } } })
    await flushPromises(); await draft(wrapper)
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await wrapper.get('[data-result-form]').trigger('submit'); await flushPromises()
    resolveOld(json(work)); await flushPromises()
    expect(wrapper.text()).toContain('Версия работы 2'); expect(wrapper.find('[data-current-result]').exists()).toBe(true)
    wrapper.unmount()
  })
  it('waits for the result DTO before mounting result controls on an older backend', async () => {
    const { wrapper } = await open({ ...expertise, result_readiness: undefined })
    expect(wrapper.find('[data-result-panel]').exists()).toBe(false)
    expect(wrapper.find('[data-production]').exists()).toBe(true)
    wrapper.unmount()
  })
})
