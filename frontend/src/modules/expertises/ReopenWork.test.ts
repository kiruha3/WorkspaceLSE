import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import { expertise, testRouter } from '../../test/intakeFixtures'
import type { Expertise } from '../../api/types'
import { hasBusyForms } from '../../shared/ui/useDirtyGuard'
import ReopenWork from './ReopenWork.vue'
import ExpertisePage from './ExpertisePage.vue'

afterEach(() => vi.restoreAllMocks())
const closed: Expertise = { ...expertise, state: 'completed', version: 8, allowed_actions: ['expertise.reopen'] }
type Write = { path: string; body: unknown; key: string | null }
async function open(work = closed, respond: (count: number) => Response | Promise<Response> = () => json({ event: { id: 'event' }, expertise: { ...closed, state: 'in_progress', version: 9, allowed_actions: [] } })) {
  const writes: Write[] = []
  const router = await testRouter('/expertises/work-1')
  const wrapper = mount(ReopenWork, { props: { expertise: work }, global: { plugins: [router], provide: { [apiKey as symbol]: new ApiClient(async (path, init) => {
    if (String(path).endsWith('/csrf/')) return json({ csrf_token: 'csrf' })
    writes.push({ path: String(path), body: JSON.parse(String(init?.body)), key: new Headers(init?.headers).get('Idempotency-Key') })
    return respond(writes.length)
  }) } } })
  return { wrapper, writes, router }
}
async function start(wrapper: Awaited<ReturnType<typeof open>>['wrapper']) {
  await wrapper.get('[data-reopen-start]').trigger('click')
  await wrapper.get('[name="reopen_reason"]').setValue('  Нажали завершение по ошибке  ')
}

describe('return a completed expertise to work', () => {
  it('does not advertise an unavailable action or one for a noncompleted work', async () => {
    for (const work of [{ ...closed, allowed_actions: [] }, { ...closed, state: 'in_progress' as const }]) {
      const { wrapper } = await open(work)
      expect(wrapper.find('[data-reopen-start]').exists()).toBe(false)
      wrapper.unmount()
    }
  })
  it('requires a reason and explicit submission; sends the version and preserves the server response', async () => {
    const { wrapper, writes } = await open()
    await wrapper.get('[data-reopen-start]').trigger('click')
    expect(wrapper.get('[data-reopen-confirm]').attributes('disabled')).toBeDefined()
    await wrapper.get('[data-reopen-form]').trigger('submit'); expect(writes).toHaveLength(0)
    await wrapper.get('[name="reopen_reason"]').setValue('  Ошибка завершения  ')
    expect(writes).toHaveLength(0)
    await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(writes[0]).toMatchObject({ path: '/api/v1/expertises/work-1/reopen/', body: { expected_version: 8, reason: 'Ошибка завершения' } })
    expect(writes[0]?.key).toBeTruthy()
    expect(wrapper.emitted('updated')?.[0]?.[0]).toMatchObject({ state: 'in_progress', version: 9 })
    expect(wrapper.find('[data-reopen-form]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('does not double submit and blocks navigation while waiting', async () => {
    let resolve!: (value: Response) => void
    const { wrapper, writes, router } = await open(closed, () => new Promise(done => { resolve = done }))
    await start(wrapper); await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(hasBusyForms()).toBe(true)
    await wrapper.get('[data-reopen-form]').trigger('submit'); expect(writes).toHaveLength(1)
    await router.push('/expertises'); expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    resolve(json({ event: { id: 'event' }, expertise: { ...closed, state: 'in_progress' } })); await flushPromises()
    expect(hasBusyForms()).toBe(false); wrapper.unmount()
  })
  it('retries an uncertain response with the exact same payload and command key', async () => {
    const { wrapper, writes } = await open(closed, count => count === 1 ? Promise.reject(new TypeError('offline')) : json({ event: { id: 'event' }, expertise: { ...closed, state: 'in_progress' } }))
    await start(wrapper); await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Результат запроса неизвестен')
    await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]); wrapper.unmount()
  })
  it('requires an explicit new version after a conflict, preserving the reason', async () => {
    const { wrapper, writes } = await open(closed, count => count === 1 ? json({ code: 'version_conflict', message: 'Версия изменена' }, 409) : json({ event: { id: 'event' }, expertise: { ...closed, state: 'in_progress' } }))
    await start(wrapper); await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-reopen-form]').trigger('submit'); expect(writes).toHaveLength(1)
    await wrapper.setProps({ expertise: { ...closed, version: 9 } })
    await wrapper.get('[data-reopen-use-version]').trigger('click')
    await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(writes[1]?.body).toEqual({ expected_version: 9, reason: 'Нажали завершение по ошибке' })
    expect(writes[1]?.key).not.toBe(writes[0]?.key); wrapper.unmount()
  })
  it('hides the command after permission loss without discarding an existing draft', async () => {
    const { wrapper, writes } = await open(); await start(wrapper)
    await wrapper.setProps({ expertise: { ...closed, allowed_actions: [] } })
    await wrapper.get('[data-reopen-form]').trigger('submit'); expect(writes).toHaveLength(0)
    expect((wrapper.get('[name="reopen_reason"]').element as HTMLTextAreaElement).value).toContain('ошибке')
    wrapper.unmount()
  })
  it('shows the historical return event without requiring permission to reopen', async () => {
    const { wrapper } = await open({ ...closed, state: 'suspended', allowed_actions: [], reopening_history: [{ id: 'event', closure_id: null, historical_completed_on: '2026-10-10', historical_return_decided_on: null, restored_state: 'suspended', actor: { id: 'user', full_name: 'Начальник отдела' }, created_at: '2026-10-29T09:00:00Z', reason: 'Неверное завершение' }] })
    expect(wrapper.get('[data-reopening-history]').text()).toContain('Начальник отдела')
    expect(wrapper.text()).toContain('Неверное завершение')
    expect(wrapper.text()).toContain('Приостановлена')
    expect(wrapper.text()).toContain('10.10.2026'); wrapper.unmount()
  })
  it('does not overwrite newer card data with a delayed success response', async () => {
    let resolve!: (value: Response) => void
    const { wrapper } = await open(closed, () => new Promise(done => { resolve = done }))
    await start(wrapper); await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    await wrapper.setProps({ expertise: { ...closed, version: 10, state: 'in_progress', allowed_actions: [] } })
    resolve(json({ event: { id: 'event' }, expertise: { ...closed, version: 9, state: 'in_progress' } })); await flushPromises()
    expect(wrapper.emitted('updated')).toBeUndefined()
    expect(wrapper.emitted('refresh')).toHaveLength(1); wrapper.unmount()
  })
  it('integrates the command in the result tab and reports a newer completed state on replay truthfully', async () => {
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [router, sessionWith('expertise.view')], provide: { [apiKey as symbol]: new ApiClient(async (path, init) => {
      if (String(path).endsWith('/csrf/')) return json({ csrf_token: 'csrf' })
      if (init?.method === 'POST') return json({ event: { id: 'old-return' }, expertise: { ...closed, version: 11 } })
      return json(closed)
    }) } } })
    await flushPromises()
    await wrapper.get('[data-card-tab="result"]').trigger('click')
    expect(wrapper.get('[data-reopen-start]').isVisible()).toBe(true)
    await start(wrapper); await wrapper.get('[data-reopen-form]').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Команда возврата уже выполнена ранее. Текущее состояние — «Завершена»')
    expect(wrapper.text()).not.toContain('Экспертиза возвращена в работу. История и документы сохранены.')
    wrapper.unmount()
  })
})
