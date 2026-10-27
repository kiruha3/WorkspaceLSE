import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { json, sessionWith } from '../test/fixtures'
import LoginPage from './LoginPage.vue'

afterEach(() => vi.unstubAllGlobals())
describe('personal login', () => {
  it('keeps the login form and displays server rejection without a successful navigation', async () => {
    vi.stubGlobal('fetch', async (input: unknown) => String(input).endsWith('/csrf/') ? json({ csrf_token: 'token' }) : json({ code: 'invalid_credentials', message: 'Неверный логин или пароль.', field_errors: {} }, 400))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/login', component: LoginPage }, { path: '/workspace', component: { template: '<p>Рабочее место</p>' } }] })
    await router.push('/login')
    const pinia = sessionWith()
    const wrapper = mount(LoginPage, { global: { plugins: [pinia, router] } })
    expect(wrapper.find('[name="username"]').exists()).toBe(true)
    await wrapper.get('[name="username"]').setValue('tester')
    await wrapper.get('[name="password"]').setValue('test-only')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Неверный логин или пароль')
    expect(router.currentRoute.value.path).toBe('/login')
    expect((wrapper.get('[name="username"]').element as HTMLInputElement).value).toBe('tester')
  })
})
