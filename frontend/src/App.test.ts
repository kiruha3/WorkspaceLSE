import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'
import { sessionWith, json } from './test/fixtures'
import { useDirtyGuard } from './shared/ui/useDirtyGuard'
import SettingsPage from './modules/settings/SettingsPage.vue'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
describe('session exit', () => {
  it('groups administrative navigation under Settings and keeps all permitted sections reachable', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace','/settings','/references','/people','/access','/roles','/imports','/reports','/report-plans'].map(path => ({ path, component: path === '/settings' ? SettingsPage : { template: '<p>Раздел</p>' } })) })
    await router.push('/settings')
    const pinia = sessionWith('employees.view','references.view','users.view','access.roles.view')
    const wrapper = mount(App, { global: { plugins: [pinia, router] } })
    await flushPromises()
    const nav = wrapper.get('nav[aria-label="Основное меню"]')
    expect(nav.find('a[href="/settings"]').exists()).toBe(true)
    for (const path of ['/people','/references','/access','/roles']) {
      expect(nav.find(`a[href="${path}"]`).exists()).toBe(false)
      expect(wrapper.get(`.settings-grid a[href="${path}"]`).isVisible()).toBe(true)
    }
    await wrapper.get('[data-setting="people"]').trigger('click'); await flushPromises()
    expect(router.currentRoute.value.path).toBe('/people')
    expect(nav.get('a[href="/settings"]').classes()).toContain('router-link-active')
    wrapper.unmount()
  })
  it('keeps the settings entry and only the employee card for an HR-only reader', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/settings', component: SettingsPage }, { path: '/people', component: { template: '<p>Сотрудники</p>' } }, { path: '/workspace', component: { template: '<p>Работа</p>' } }] })
    await router.push('/settings')
    const wrapper = mount(App, { global: { plugins: [sessionWith('employees.view'), router] } })
    await flushPromises()
    expect(wrapper.get('nav a[href="/settings"]').isVisible()).toBe(true)
    expect(wrapper.findAll('[data-setting]')).toHaveLength(1)
    expect(wrapper.get('[data-setting="people"]').attributes('href')).toBe('/people')
    wrapper.unmount()
  })
  it.each(['/references','/people','/access','/roles','/settings/storage','/imports/source-settings'])('marks Settings for the administrative route %s', async path => {
    const router = createRouter({ history: createMemoryHistory(), routes: [...new Set(['/workspace','/settings',path])].map(value => ({ path: value, component: { template: '<p>Раздел</p>' } })) })
    await router.push(path)
    const wrapper = mount(App, { global: { plugins: [sessionWith('access.roles.view'), router] } })
    expect(wrapper.get('nav a[href="/settings"]').classes()).toContain('router-link-active')
    wrapper.unmount()
  })
  it('does not expose settings navigation or administrative cards to an expertise-only reader', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace','/expertises'].map(path => ({ path, component: { template: '<p>Работа</p>' } })) })
    await router.push('/workspace')
    const wrapper = mount(App, { global: { plugins: [sessionWith('expertise.view'), router] } })
    expect(wrapper.find('nav a[href="/settings"]').exists()).toBe(false)
    expect(wrapper.find('nav a[href="/people"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('offers the intake and expertise registries only under their independent read rights', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/intake', '/expertises'].map(path => ({ path, component: { template: '<p>Раздел</p>' } })) })
    await router.push('/workspace')
    const wrapper = mount(App, { global: { plugins: [sessionWith('receipts.view'), router] } })
    expect(wrapper.find('nav a[href="/intake"]').exists()).toBe(true)
    expect(wrapper.find('nav a[href="/expertises"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('does not end the server session if the user keeps an unsaved form', async () => {
    let requests = 0
    vi.stubGlobal('fetch', async () => { requests++; return json({ csrf_token: 'token' }) })
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const dirtyForm = mount(defineComponent({ setup() { useDirtyGuard(() => true); return () => null } }))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/workspace', component: { template: '<p>Рабочее место</p>' } }, { path: '/login', component: { template: '<p>Вход</p>' } }] })
    await router.push('/workspace')
    const wrapper = mount(App, { global: { plugins: [sessionWith(), router] } })
    try {
      await wrapper.get('[aria-label="Выйти из системы"]').trigger('click')
      await flushPromises()
      expect(requests).toBe(0)
      expect(router.currentRoute.value.path).toBe('/workspace')
    } finally { wrapper.unmount(); dirtyForm.unmount() }
  })
})
