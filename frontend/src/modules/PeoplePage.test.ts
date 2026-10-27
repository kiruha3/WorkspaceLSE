import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../api/client'
import { employee, json, page, sessionWith } from '../test/fixtures'
import PeoplePage from './PeoplePage.vue'

afterEach(() => vi.restoreAllMocks())

describe('people registry', () => {
  it('shows one employee row with qualified and training specialties separately', async () => {
    const client = new ApiClient(async () => json(page([employee])))
    const wrapper = mount(PeoplePage, { global: { plugins: [sessionWith('employees.view')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(1)
    const row = wrapper.get('[data-employee-row]')
    expect(row.text()).toContain('18.1')
    expect(row.text()).toContain('13.1')
    expect(row.get('[data-training]').text()).toContain('13.1')
    expect(row.get('[data-qualified]').text()).toContain('18.1')
  })

  it('confirms a training specialty only through the authorized qualify command', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/qualify/')) { writes.push({ path, body: JSON.parse(String(init?.body)) }); return json({ ...employee.specialties[1], status: 'qualified', version: 2 }) }
      if (path.includes('/employees/employee-1/')) return json(employee)
      return json(page([employee]))
    })
    const wrapper = mount(PeoplePage, { global: { plugins: [sessionWith('employees.view', 'specialties.qualify')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(1)
    await wrapper.get('[data-open-employee="employee-1"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-qualify="es-2"]').trigger('click')
    await wrapper.get('[name="qualified_at"]').setValue('2026-10-28')
    await wrapper.get('[name="qualification_basis"]').setValue('Протокол комиссии № 1')
    await wrapper.get('[data-confirm-qualification]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/employee-specialties/es-2/qualify/', body: { expected_version: 1, qualified_at: '2026-10-28', basis: 'Протокол комиссии № 1' } }])
  })

  it('replaces the registry with a dedicated card and returns to the same search and page', async () => {
    const listRequests: string[] = []
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/employees/employee-1/')) return json(employee)
      listRequests.push(path)
      return json({ count: 30, next: path.includes('page=2') ? null : '/api/v1/employees/?page=2', previous: path.includes('page=2') ? '/api/v1/employees/?page=1' : null, results: [employee] })
    })
    const wrapper = mount(PeoplePage, { global: { plugins: [sessionWith('employees.view')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('input[type="search"]').setValue('Тестовый')
    await wrapper.get('form.toolbar').trigger('submit')
    await flushPromises()
    await wrapper.get('.pagination').findAll('button')[1]!.trigger('click')
    await flushPromises()
    expect(wrapper.get('.pagination').text()).toContain('Страница 2')
    await wrapper.get('[data-open-employee="employee-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(0)
    expect(wrapper.get('.employee-card h2').text()).toBe('Тестовый сотрудник')
    expect(wrapper.find('input[type="search"]').exists()).toBe(false)
    await wrapper.get('[data-back-to-people]').trigger('click')
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(1)
    expect((wrapper.get('input[type="search"]').element as HTMLInputElement).value).toBe('Тестовый')
    expect(wrapper.get('.pagination').text()).toContain('Страница 2')
    expect(listRequests).toHaveLength(3)
    wrapper.unmount()
  })

  it('keeps a dirty card open if the user declines returning to the list', async () => {
    const client = new ApiClient(async input => String(input).includes('/employees/employee-1/') ? json(employee) : json(page([employee])))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mount(PeoplePage, { global: { plugins: [sessionWith('employees.view', 'employees.update')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[data-open-employee="employee-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-back-to-people]').exists()).toBe(true)
    await wrapper.get('.employee-card input:not([type])').setValue('Несохранённое имя')
    await wrapper.get('[data-back-to-people]').trigger('click')
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(0)
    expect((wrapper.get('.employee-card input:not([type])').element as HTMLInputElement).value).toBe('Несохранённое имя')
    confirm.mockReturnValue(true)
    await wrapper.get('[data-back-to-people]').trigger('click')
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('opens the new employee form in place of the registry and guards its back action', async () => {
    const client = new ApiClient(async () => json(page([employee])))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const wrapper = mount(PeoplePage, { global: { plugins: [sessionWith('employees.view', 'employees.create')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('.page-heading .button-primary').trigger('click')
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(0)
    expect(wrapper.get('.narrow-card h2').text()).toBe('Новый сотрудник')
    await wrapper.get('[name="full_name"]').setValue('Новый сотрудник')
    await wrapper.get('[data-back-to-people]').trigger('click')
    expect(wrapper.find('[name="full_name"]').exists()).toBe(true)
    confirm.mockReturnValue(true)
    await wrapper.get('[data-back-to-people]').trigger('click')
    expect(wrapper.findAll('[data-employee-row]')).toHaveLength(1)
    wrapper.unmount()
  })
})
