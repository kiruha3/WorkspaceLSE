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
  const wrapper = mount(HomePage, { attachTo: document.body, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: new ApiClient(async input => { const path = String(input); paths.push(path); return respond(path, paths.length) }) } } })
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
  it('collapses the reminders while keeping their heading and total visible', async () => {
    const { wrapper, paths } = await open(() => json(page([item])))
    const section = wrapper.get('[data-incomplete-expertises]')
    const toggle = section.get('[data-toggle-incomplete]')
    const details = section.get('[data-incomplete-details]')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(toggle.attributes('aria-controls')).toBe(details.attributes('id'))
    expect(details.isVisible()).toBe(true)

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.text()).toContain('Развернуть')
    expect(details.isVisible()).toBe(false)
    expect(section.get('h2').isVisible()).toBe(true)
    expect(section.get('[data-incomplete-count]').text()).toBe('Экспертиз: 1')
    expect(section.get('[data-incomplete-count]').isVisible()).toBe(true)

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
    expect(details.isVisible()).toBe(true)
    expect(section.get(`[data-incomplete-work="${item.id}"] a`).isVisible()).toBe(true)
    expect(paths).toEqual(['/api/v1/expertises/incomplete/?page=1'])
    wrapper.unmount()
  })
  it('keeps the current reminder page when the list is folded and reopened', async () => {
    const second = { ...item, id: 'second-work', registration_number: '152/4-1-26' }
    const { wrapper, paths } = await open(path => json(path.endsWith('page=2')
      ? { count: 26, next: null, previous: '/expertises/incomplete/?page=1', results: [second] }
      : { count: 26, next: '/expertises/incomplete/?page=2', previous: null, results: [item] }))
    const section = wrapper.get('[data-incomplete-expertises]')
    await section.get('.pagination').findAll('button').find(button => button.text() === 'Далее')!.trigger('click')
    await flushPromises()
    expect(section.get('.pagination').text()).toContain('Страница 2')

    await section.get('[data-toggle-incomplete]').trigger('click')
    await section.get('[data-toggle-incomplete]').trigger('click')
    expect(section.get('.pagination').text()).toContain('Страница 2')
    expect(section.get('[data-incomplete-work="second-work"]').isVisible()).toBe(true)
    expect(section.get('[data-incomplete-count]').text()).toBe('Экспертиз: 26')
    expect(paths).toEqual(['/api/v1/expertises/incomplete/?page=1', '/api/v1/expertises/incomplete/?page=2'])
    wrapper.unmount()
  })
  it('keeps errors and refresh available when folded without showing a false zero', async () => {
    const { wrapper } = await open((_path, count) => count === 1
      ? json({ code: 'temporary', message: 'Не удалось получить список' }, 503)
      : json(page([item])))
    const section = wrapper.get('[data-incomplete-expertises]')
    await section.get('[data-toggle-incomplete]').trigger('click')
    expect(section.get('[role="alert"]').isVisible()).toBe(true)
    expect(section.find('[data-incomplete-count]').exists()).toBe(false)
    expect(section.get('[data-refresh-incomplete]').isVisible()).toBe(true)

    await section.get('[data-refresh-incomplete]').trigger('click'); await flushPromises()
    expect(section.find('[role="alert"]').exists()).toBe(false)
    expect(section.get('[data-incomplete-count]').text()).toBe('Экспертиз: 1')
    expect(section.get('[data-incomplete-details]').isVisible()).toBe(false)
    wrapper.unmount()
  })
})
