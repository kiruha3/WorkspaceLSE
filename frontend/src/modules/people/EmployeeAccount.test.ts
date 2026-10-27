import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { apiKey, ApiClient } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import EmployeeAccount from './EmployeeAccount.vue'

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
})
