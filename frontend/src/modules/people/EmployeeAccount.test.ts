import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiKey, ApiClient } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import EmployeeAccount from './EmployeeAccount.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())

describe('employee personal account', () => {
  it.each(['users.create', 'users.deactivate'])('looks up the existing account under %s without a separate view grant', async permission => {
    const client = new ApiClient(async () => json({ id: 'u-2', username: 'existing-user', is_active: true }))
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith(permission)], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('existing-user')
    expect(wrapper.find('[data-create-account]').exists()).toBe(false)
    expect(wrapper.find('[data-toggle-account]').exists()).toBe(permission === 'users.deactivate')
    wrapper.unmount()
  })

  it('creates an account without roles and clears the password after server confirmation', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ path: String(input), body: JSON.parse(String(init.body)) }); return json({ id: 'u-2', username: 'personal-user', is_active: true }, 201) }
      return json(null)
    })
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('users.view', 'users.create')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[name="new_username"]').exists()).toBe(true)
    await wrapper.get('[name="new_username"]').setValue('personal-user')
    await wrapper.get('[name="new_password"]').setValue('temporary-test-only')
    await wrapper.get('[data-create-account]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/employees/employee-1/account/', body: { username: 'personal-user', password: 'temporary-test-only' } }])
    expect(wrapper.text()).toContain('personal-user')
    expect(wrapper.find('[name="new_password"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('temporary-test-only')
    expect(wrapper.find('[data-toggle-account]').exists()).toBe(false)
  })

  it('blocks the account with a reason independently from employee activity or roles', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'PATCH') { writes.push(JSON.parse(String(init.body))); return json({ id: 'u-2', username: 'personal-user', is_active: false }) }
      return json({ id: 'u-2', username: 'personal-user', is_active: true })
    })
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('users.view', 'users.deactivate')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-toggle-account]').exists()).toBe(true)
    await wrapper.get('[data-toggle-account]').trigger('click')
    await wrapper.get('[name="account_state_reason"]').setValue('Приказ о блокировке')
    await wrapper.get('[data-account-state-form]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ is_active: false, reason: 'Приказ о блокировке' }])
    expect(wrapper.text()).toContain('Вход заблокирован')
  })

  it('resets an existing password with the reset right and clears the secret after success', async () => {
    const writes: unknown[] = []
    const value = { id: 'u-2', username: 'existing-user', is_active: true }
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') writes.push({ path: String(input), body: JSON.parse(String(init.body)) })
      return json(value)
    })
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('users.reset_password')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('existing-user')
    expect(wrapper.find('[data-create-account]').exists()).toBe(false)
    await wrapper.get('[data-reset-account]').trigger('click')
    expect(writes).toHaveLength(0)
    await wrapper.get('[name="reset_password"]').setValue('Replacement-test-only-password9!')
    await wrapper.get('[name="reset_password_confirm"]').setValue('Replacement-test-only-password9!')
    await wrapper.get('[data-reset-account-form]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/employees/employee-1/account/reset-password/', body: { password: 'Replacement-test-only-password9!' } }])
    expect(wrapper.find('[name="reset_password"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Пароль изменён')
    expect(wrapper.text()).not.toContain('Replacement-test-only-password9!')
    expect(wrapper.vm.dirty).toBe(false)
  })

  it.each(['users.view', 'users.create', 'users.deactivate'])('does not offer password reset with only %s', async permission => {
    const client = new ApiClient(async () => json({ id: 'u-2', username: 'existing-user', is_active: true }))
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith(permission)], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-reset-account]').exists()).toBe(false)
  })

  it('does not send mismatched passwords and preserves the draft on a server failure', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ message: 'Право сброса отозвано' }, 403) }
      return json({ id: 'u-2', username: 'existing-user', is_active: true })
    })
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('users.reset_password')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[data-reset-account]').trigger('click')
    await wrapper.get('[name="reset_password"]').setValue('Replacement-test-only-password9!')
    await wrapper.get('[name="reset_password_confirm"]').setValue('Different-test-only-password9!')
    await wrapper.get('[data-reset-account-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(0)
    expect(wrapper.get('[role="alert"]').text()).toContain('не совпадают')
    await wrapper.get('[name="reset_password_confirm"]').setValue('Replacement-test-only-password9!')
    await wrapper.get('[data-reset-account-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1)
    expect(wrapper.get('[role="alert"]').text()).toContain('Право сброса отозвано')
    expect((wrapper.get('[name="reset_password"]').element as HTMLInputElement).value).toBe('Replacement-test-only-password9!')
    expect(wrapper.vm.dirty).toBe(true)
  })

  it('confirms discarding a reset draft and clears it after cancellation', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const client = new ApiClient(async () => json({ id: 'u-2', username: 'existing-user', is_active: true }))
    const wrapper = mount(EmployeeAccount, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('users.reset_password')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[data-reset-account]').trigger('click')
    await wrapper.get('[name="reset_password"]').setValue('Draft-test-only-password9!')
    await wrapper.get('[data-cancel-password-reset]').trigger('click')
    expect(wrapper.find('[data-reset-account-form]').exists()).toBe(true)
    confirm.mockReturnValue(true)
    await wrapper.get('[data-cancel-password-reset]').trigger('click')
    expect(wrapper.find('[data-reset-account-form]').exists()).toBe(false)
    expect(wrapper.vm.dirty).toBe(false)
    await wrapper.get('[data-reset-account]').trigger('click')
    expect((wrapper.get('[name="reset_password"]').element as HTMLInputElement).value).toBe('')
  })
})
