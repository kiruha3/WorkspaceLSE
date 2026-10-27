import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'
import { sessionWith, json } from './test/fixtures'
import { useDirtyGuard } from './shared/ui/useDirtyGuard'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
describe('session exit', () => {
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
