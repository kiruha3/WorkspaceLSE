import { flushPromises, mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { ApiClient, apiKey } from '../api/client'
import { json, page, sessionWith } from '../test/fixtures'
import { useSessionStore } from '../stores/session'
import HomePage from './HomePage.vue'

const item = { id: '3c04d146-bede-4641-b422-075b804bcabf', registration_number: '151/4-1-26', state: 'completed', missing: [{ code: 'result_document_missing', message: 'Не прикреплён итоговый документ.' }, { code: 'complexity_missing', message: 'Не указана категория сложности.' }] }
async function open(respond: (path: string, count: number) => Response | Promise<Response>, allowed = true) {
  const pinia = sessionWith(...(allowed ? ['expertise.view'] : []))
  useSessionStore().user!.supported_modules = ['expertise_completeness']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: HomePage }, { path: '/expertises/:id', component: { template: '<div>Карточка</div>' } }, { path: '/expertises', component: { template: '<div>Реестр</div>' } }] })
  await router.push('/'); await router.isReady()
  const paths: string[] = []
  const wrapper = mount(HomePage, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: new ApiClient(async input => { const path = String(input); paths.push(path); return respond(path, paths.length) }) } } })
  await flushPromises()
  return { wrapper, paths }
}

describe('per-expertise reminders on the personal workplace', () => {
  it('groups missing data under the work number and links to its real card', async () => {
    const { wrapper, paths } = await open(() => json(page([item])))
    const section = wrapper.get('[data-incomplete-expertises]')
    expect(section.text()).toContain('Не заполнено')
    expect(section.findAll('[data-incomplete-work]')).toHaveLength(1)
    expect(section.text()).toContain('Не прикреплён итоговый документ')
    expect(section.text()).toContain('Не указана категория сложности')
    expect(section.get(`[data-incomplete-work="${item.id}"] a`).attributes('href')).toBe(`/expertises/${item.id}?return=/`)
    expect(paths).toEqual(['/api/v1/expertises/incomplete/?page=1'])
    wrapper.unmount()
  })
  it('does not request or reveal work reminders without the view right', async () => {
    const { wrapper, paths } = await open(() => json(page([item])), false)
    expect(wrapper.find('[data-incomplete-expertises]').exists()).toBe(false)
    expect(paths).toEqual([])
    wrapper.unmount()
  })
  it('shows an empty list without fabricating missing data', async () => {
    const { wrapper } = await open(() => json(page([])))
    expect(wrapper.get('[data-incomplete-expertises]').text()).toContain('Нет незаполненных сведений')
    expect(wrapper.findAll('[data-incomplete-work]')).toHaveLength(0)
    wrapper.unmount()
  })
  it('allows refreshing a failure and removes resolved reminders', async () => {
    const { wrapper } = await open((_path, count) => count === 1 ? json({ code: 'temporary', message: 'Не удалось получить список' }, 503) : json(page([])))
    expect(wrapper.get('[data-incomplete-expertises]').text()).toContain('Не удалось получить список')
    await wrapper.get('[data-refresh-incomplete]').trigger('click'); await flushPromises()
    expect(wrapper.get('[data-incomplete-expertises]').text()).toContain('Нет незаполненных сведений')
    wrapper.unmount()
  })
  it('handles a malformed list as an error instead of rendering an empty success', async () => {
    const { wrapper } = await open(() => json({ count: 478 }))
    expect(wrapper.get('[data-incomplete-expertises]').text()).toContain('Сервер не вернул список')
    expect(wrapper.text()).not.toContain('Нет незаполненных сведений')
    wrapper.unmount()
  })
})
