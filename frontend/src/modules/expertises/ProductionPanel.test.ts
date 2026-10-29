import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import type { Expertise } from '../../api/types'
import { json, sessionWith } from '../../test/fixtures'
import { basis, expertise, testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'

afterEach(() => vi.restoreAllMocks())
const production = { as_of: '2026-10-28', counted_through: '2026-10-28', method: 'calendar_inclusive_pause_half_open_v1', calendar_days: 10, paused_days: 6, active_calendar_days: 4, initial_due_on: null, agreed_due_on: '2026-11-06', current_due_on: '2026-11-06', last_requested_due_on: '2026-11-12', overdue_calendar_days: 0 }
const work = { ...expertise, receipt: { ...expertise.receipt, received_at: '2026-10-19' }, production, suspensions: [], deadline_events: [], allowed_actions: ['expertise.suspend', 'expertise.deadline.record'] } as Expertise
const fileVersion = { id: 'file-agreement', number: 1, original_name: 'agreement.pdf', content_type: 'application/pdf', size: 8, sha256: 'abc', created_at: '2026-10-28T00:00:00Z', download_url: '/agreement/download/', preview_url: '/agreement/preview/' }
async function open(transport: typeof fetch, path = '/expertises/work-1') {
  const router = await testRouter(path)
  const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.suspend', 'expertise.resume', 'expertise.deadline.record'), router], provide: { [apiKey as symbol]: new ApiClient(transport) } } })
  await flushPromises()
  return { wrapper, router }
}
async function fillPause(wrapper: Awaited<ReturnType<typeof open>>['wrapper']) {
  await wrapper.get('[data-production-suspend]').trigger('click')
  await wrapper.get('[name="suspended_on"]').setValue('2026-10-25')
  await wrapper.get('[name="production_reason"]').setValue('Ожидание дополнительных материалов')
}

describe('production work controls', () => {
  it('labels the fixed closed count and clipped open pause without inventing a resumption', async () => {
    const pause = { id: 'pause', suspended_on: '2026-10-23', resumed_on: null, reason: 'Материалы', resume_reason: '', actor: { id: 'u', full_name: 'Эксперт' }, resumed_by: null, created_at: '2026-10-23T00:00:00Z', resumed_recorded_at: null }
    const { wrapper } = await open(async () => json({ ...work, state: 'completed', allowed_actions: [], production: { ...production, counted_through: '2026-10-25' }, suspensions: [pause] }))
    expect(wrapper.get('[data-counted-through]').text()).toContain('2026-10-25')
    expect(wrapper.get('[data-suspension-history]').text()).toContain('Ограничена окончанием 2026-10-25')
    expect(wrapper.get('[data-suspension-history]').text()).not.toContain('Возобновление внёс')
    wrapper.unmount()
  })
  it('shows server counts and distinct requested, agreed and unknown initial dates without granting session-wide actions', async () => {
    const { wrapper } = await open(async () => json({ ...work, allowed_actions: [] }))
    expect(wrapper.get('[data-production]').text()).toContain('Календарные дни')
    expect(wrapper.get('[data-calendar-days]').text()).toBe('10')
    expect(wrapper.get('[data-paused-days]').text()).toBe('6')
    expect(wrapper.get('[data-active-days]').text()).toBe('4')
    expect(wrapper.get('[data-initial-due]').text()).toBe('Неизвестен')
    expect(wrapper.get('[data-current-due]').text()).toBe('2026-11-06')
    expect(wrapper.get('[data-requested-due]').text()).toBe('2026-11-12')
    expect(wrapper.get('[data-production]').text()).toContain('2026-10-28')
    expect(wrapper.get('[data-production]').text()).not.toContain('calendar_inclusive_pause_half_open_v1')
    await wrapper.get('[data-card-tab="production"]').trigger('click')
    await wrapper.get('button[aria-label="Пояснение: Расчёт дней производства"]').trigger('focus'); await flushPromises()
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('calendar_inclusive_pause_half_open_v1')
    expect(document.querySelector('[role="tooltip"]')?.textContent).toContain('не является юридическим или рабочим сроком')
    expect(wrapper.find('[data-production-suspend]').exists()).toBe(false)
    expect(wrapper.find('[data-production-deadline]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('renders unknown closed-work counters as unknown instead of zero', async () => {
    const { wrapper } = await open(async () => json({ ...work, state: 'completed', allowed_actions: [], production: { ...production, calendar_days: null, paused_days: null, active_calendar_days: null, overdue_calendar_days: null } }))
    expect(wrapper.get('[data-calendar-days]').text()).toBe('Неизвестно')
    expect(wrapper.get('[data-paused-days]').text()).toBe('Неизвестно')
    expect(wrapper.get('[data-active-days]').text()).toBe('Неизвестно')
    wrapper.unmount()
  })

  it('posts suspension with version and key, applies fresh work and cancels an older GET', async () => {
    let reads = 0, resolveOld!: (response: Response) => void
    const old = new Promise<Response>(resolve => { resolveOld = resolve })
    const writes: { path: string; body: unknown; key: string | null }[] = []
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push({ path: String(input), body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') })
        return json({ event: { id: 'pause-1' }, expertise: { ...work, version: 2, state: 'suspended', allowed_actions: ['expertise.resume', 'expertise.deadline.record'] } })
      }
      reads++; return reads === 1 ? json(work) : old
    })
    await fillPause(wrapper)
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1)
    expect(writes[0]?.path).toBe('/api/v1/expertises/work-1/suspend/')
    expect(writes[0]?.body).toEqual({ expected_version: 1, suspended_on: '2026-10-25', reason: 'Ожидание дополнительных материалов' })
    expect(writes[0]?.key).toBeTruthy()
    expect(wrapper.find('[data-production-resume]').exists()).toBe(true)
    resolveOld(json(work)); await flushPromises()
    expect(wrapper.find('[data-production-suspend]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Версия работы 2')
    wrapper.unmount()
  })

  it('records resume and renders both actors, boundaries and reasons from history', async () => {
    const writes: unknown[] = []
    const suspension = { id: 'pause-1', suspended_on: '2026-10-25', resumed_on: null, reason: 'Нужны материалы', resume_reason: '', actor: { id: 'u-1', full_name: 'Эксперт первый' }, resumed_by: null, created_at: '2026-10-25T00:00:00Z', resumed_recorded_at: null }
    const paused = { ...work, state: 'suspended', allowed_actions: ['expertise.resume'], suspensions: [suspension] }
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push(JSON.parse(String(init.body)))
        expect(String(input)).toBe('/api/v1/expertises/work-1/resume/')
        expect(new Headers(init.headers).get('Idempotency-Key')).toBeTruthy()
        return json({ event: { id: 'pause-1' }, expertise: { ...work, version: 2, suspensions: [{ ...suspension, resumed_on: '2026-10-28', resume_reason: 'Материалы получены', resumed_by: { id: 'u-2', full_name: 'Делопроизводитель' }, resumed_recorded_at: '2026-10-28T00:00:00Z' }] } })
      }
      return json(paused)
    })
    await wrapper.get('[data-production-resume]').trigger('click')
    expect(wrapper.get('[name="resumed_on"]').attributes('min')).toBe('2026-10-25')
    await wrapper.get('[name="resumed_on"]').setValue('2026-10-28')
    await wrapper.get('[name="production_reason"]').setValue('Материалы получены')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, resumed_on: '2026-10-28', reason: 'Материалы получены' }])
    const history = wrapper.get('[data-suspension-history]').text()
    for (const value of ['2026-10-25', '2026-10-28', 'Эксперт первый', 'Делопроизводитель', 'Нужны материалы', 'Материалы получены']) expect(history).toContain(value)
    wrapper.unmount()
  })

  it('replays the exact lost-response command after unchanged explicit reload even when state actions change', async () => {
    const writes: { body: string; key: string | null }[] = []
    let version = 1
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') })
        if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') }
        return json({ event: { id: 'pause-1' }, expertise: { ...work, version, state: 'suspended', allowed_actions: ['expertise.resume'] } })
      }
      return json(version === 1 ? work : { ...work, version, state: 'suspended', allowed_actions: ['expertise.resume'] })
    })
    await fillPause(wrapper)
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    expect((wrapper.get('[name="production_reason"]').element as HTMLTextAreaElement).value).toBe('Ожидание дополнительных материалов')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2)
    expect(writes[1]).toEqual(writes[0])
    expect(JSON.parse(writes[1]!.body).expected_version).toBe(1)
    expect(wrapper.find('[data-production-form]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('preserves a lost deadline command for whitespace-only reason edits after reload', async () => {
    const writes: { body: string; key: string | null }[] = []
    let version = 1
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') })
        if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') }
        return json({ event: { id: 'deadline-1' }, expertise: { ...work, version } })
      }
      return json({ ...work, version })
    })
    await wrapper.get('[data-production-deadline]').trigger('click')
    await wrapper.get('[name="due_on"]').setValue('2026-11-12')
    await wrapper.get('[name="production_reason"]').setValue('Основание срока')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    await wrapper.get('[name="production_reason"]').setValue('  Основание срока  ')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2)
    expect(writes[1]).toEqual(writes[0])
    wrapper.unmount()
  })

  it('preserves a prepared agreement attempt for whitespace-only document title edits', async () => {
    const writes: { body: string; key: string | null }[] = []
    let version = 1, documents = 0
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (String(input).endsWith('/documents/')) {
        documents++
        return json({ ...basis, id: 'agreement-1', kind: 'deadline_agreement', title: 'Согласование' }, 201)
      }
      if (init?.method === 'POST') {
        writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') })
        if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') }
        return json({ event: { id: 'deadline-1' }, expertise: { ...work, version } })
      }
      return json({ ...work, version })
    })
    await wrapper.get('[data-production-deadline]').trigger('click')
    await wrapper.get('[name="deadline_kind"]').setValue('agreement')
    await wrapper.get('[name="due_on"]').setValue('2026-11-12')
    await wrapper.get('[name="production_reason"]').setValue('Основание срока')
    await wrapper.get('[name="document_title"]').setValue('Согласование')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    await wrapper.get('[name="document_title"]').setValue('  Согласование  ')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(documents).toBe(1)
    expect(writes).toHaveLength(2)
    expect(writes[1]).toEqual(writes[0])
    wrapper.unmount()
  })

  it('retains conflict drafts and uses a new key and current version only after a payload edit', async () => {
    const writes: { body: Record<string, unknown>; key: string | null }[] = []
    let version = 1
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') })
        return json({ code: 'version_conflict', message: 'Обновите карточку', field_errors: {} }, 409)
      }
      return json({ ...work, version })
    })
    await fillPause(wrapper)
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    version = 2
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    expect(writes).toHaveLength(1)
    expect((wrapper.get('[name="production_reason"]').element as HTMLTextAreaElement).value).toBe('Ожидание дополнительных материалов')
    await wrapper.get('[name="production_reason"]').setValue('Уточнённая причина')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes[1]!.body).toEqual({ expected_version: 2, suspended_on: '2026-10-25', reason: 'Уточнённая причина' })
    expect(writes[1]!.key).not.toBe(writes[0]!.key)
    wrapper.unmount()
  })

  it('keeps requests separate from the effective date and sends optional evidence as null', async () => {
    const writes: unknown[] = []
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        expect(String(input)).toBe('/api/v1/expertises/work-1/deadline-events/')
        expect(new Headers(init.headers).get('Idempotency-Key')).toBeTruthy()
        writes.push(JSON.parse(String(init.body)))
        return json({ event: { id: 'deadline-1' }, expertise: { ...work, version: 2, production: { ...production, last_requested_due_on: '2026-11-20' } } })
      }
      return json(work)
    })
    await wrapper.get('[data-production-deadline]').trigger('click')
    await wrapper.get('[name="deadline_kind"]').setValue('request')
    await wrapper.get('[name="recorded_on"]').setValue('2026-10-28')
    await wrapper.get('[name="due_on"]').setValue('2026-11-20')
    await wrapper.get('[name="production_reason"]').setValue('Запрошены дополнительные исследования')
    expect(wrapper.get('[name="due_on"]').attributes('max')).toBeUndefined()
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, kind: 'request', recorded_on: '2026-10-28', due_on: '2026-11-20', reason: 'Запрошены дополнительные исследования', document_id: null }])
    expect(wrapper.get('[data-current-due]').text()).toBe('2026-11-06')
    expect(wrapper.get('[data-requested-due]').text()).toBe('2026-11-20')
    wrapper.unmount()
  })

  it('requires saved agreement evidence and retains its document, file and reason through upload loss and a work conflict', async () => {
    let documentWrites = 0, version = 1
    const uploads: { key: string | null; version: FormDataEntryValue | null }[] = [], deadlines: Record<string, unknown>[] = []
    const { wrapper } = await open(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/documents/')) {
        documentWrites++
        expect(JSON.parse(String(init?.body))).toEqual({ kind: 'deadline_agreement', title: 'Письмо о согласовании', source_kind: 'uploaded_copy', department_id: 'd-4' })
        return json({ ...basis, id: 'agreement-1', kind: 'deadline_agreement', title: 'Письмо о согласовании', source_kind: 'uploaded_copy' }, 201)
      }
      if (path.endsWith('/versions/')) {
        uploads.push({ key: new Headers(init?.headers).get('Idempotency-Key'), version: (init?.body as FormData).get('expected_version') })
        if (uploads.length === 1) throw new TypeError('Ответ загрузки потерян')
        return json(fileVersion, 201)
      }
      if (init?.method === 'POST') {
        deadlines.push(JSON.parse(String(init.body)))
        return json({ code: 'version_conflict', message: 'Обновите карточку', field_errors: {} }, 409)
      }
      return json({ ...work, version })
    })
    await wrapper.get('[data-production-deadline]').trigger('click')
    await wrapper.get('[name="deadline_kind"]').setValue('agreement')
    expect(wrapper.get('[name="document_kind"]').element).toHaveProperty('value', 'deadline_agreement')
    expect(wrapper.find('[name="document_kind"] [value="deadline_request"]').exists()).toBe(false)
    await wrapper.get('[name="recorded_on"]').setValue('2026-10-28')
    await wrapper.get('[name="due_on"]').setValue('2026-11-20')
    await wrapper.get('[name="production_reason"]').setValue('Срок согласован письмом')
    await wrapper.get('[name="document_title"]').setValue('Письмо о согласовании')
    await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(documentWrites).toBe(0)
    expect(deadlines).toHaveLength(0)
    Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['evidence'], 'agreement.pdf')] })
    await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(deadlines).toHaveLength(0)
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(uploads).toHaveLength(2)
    expect(uploads[0]).toEqual(uploads[1])
    expect(documentWrites).toBe(1)
    expect(deadlines[0]?.document_id).toBe('agreement-1')
    version = 2
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Письмо о согласовании')
    expect((wrapper.get('[name="production_reason"]').element as HTMLTextAreaElement).value).toBe('Срок согласован письмом')
    expect(wrapper.text()).toContain('Файл сохранён')
    expect(deadlines).toHaveLength(1)
    wrapper.unmount()
  })

  it('uses an existing paper original for agreement and displays saved or restricted deadline evidence', async () => {
    const writes: Record<string, unknown>[] = []
    const { wrapper } = await open(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        writes.push(JSON.parse(String(init.body)))
        return json({ event: { id: 'deadline-1' }, expertise: { ...work, version: 2, deadline_events: [
          { id: 'deadline-1', kind: 'agreement', recorded_on: '2026-10-28', due_on: '2026-11-20', reason: 'Согласовано', actor: { id: 'u-1', full_name: 'Эксперт первый' }, created_at: '2026-10-28T00:00:00Z', document: { ...basis, kind: 'deadline_agreement', title: 'Подтверждение', versions: [fileVersion] } },
          { id: 'deadline-0', kind: 'request', recorded_on: '2026-10-27', due_on: '2026-11-20', reason: 'Запрос', actor: { id: 'u-1', full_name: 'Эксперт первый' }, created_at: '2026-10-27T00:00:00Z', document: { id: 'private', restricted: true } },
        ] } })
      }
      return json(work)
    })
    await wrapper.get('[data-production-deadline]').trigger('click')
    await wrapper.get('[name="deadline_kind"]').setValue('agreement')
    await wrapper.get('[name="production_document"]').setValue('document-1')
    await wrapper.get('[name="recorded_on"]').setValue('2026-10-28')
    await wrapper.get('[name="due_on"]').setValue('2026-11-20')
    await wrapper.get('[name="production_reason"]').setValue('Согласовано')
    await wrapper.get('[data-production-form]').trigger('submit'); await flushPromises()
    expect(writes[0]?.document_id).toBe('document-1')
    expect(wrapper.get('[data-deadline-history]').text()).toContain('Согласование срока')
    expect(wrapper.get('[data-deadline-history]').text()).toContain('Доступ к документу ограничен')
    expect(wrapper.find('iframe').exists()).toBe(false)
    await wrapper.get('[data-card-tab="production"]').trigger('click')
    ;(wrapper.get('[data-deadline-history]').element as HTMLDetailsElement).open = true
    await wrapper.get('[data-deadline-history] [data-document-details-toggle]').trigger('click')
    expect(wrapper.get('iframe').attributes('src')).toBe('/agreement/preview/')
    expect(wrapper.find('a[href="/agreement/download/"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('guards unsaved production drafts and clears them only on confirmed navigation to another work', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await open(async () => json(work))
    await fillPause(wrapper)
    await router.push('/expertises/work-2'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    expect(confirm).toHaveBeenCalled()
    confirm.mockReturnValue(true)
    await router.push('/expertises/work-2'); await flushPromises()
    expect(wrapper.find('[name="production_reason"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('guards a changed factual date even before a reason has been entered', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await open(async () => json(work))
    await wrapper.get('[data-production-suspend]').trigger('click')
    await wrapper.get('[name="suspended_on"]').setValue('2026-10-25')
    await router.push('/expertises'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    expect((wrapper.get('[name="suspended_on"]').element as HTMLInputElement).value).toBe('2026-10-25')
    wrapper.unmount()
  })
})
