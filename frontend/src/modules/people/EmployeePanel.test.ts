import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { apiKey, ApiClient } from '../../api/client'
import { employee, json, sessionWith } from '../../test/fixtures'
import EmployeePanel from './EmployeePanel.vue'

describe('employee edits', () => {
  it('does not ask to update the name when the operator can only deactivate', async () => {
    let payload: unknown
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      payload = JSON.parse(String(init?.body))
      return json({ ...employee, is_active: false, version: 3 })
    })
    const wrapper = mount(EmployeePanel, { props: { employee }, global: { plugins: [sessionWith('employees.deactivate')], provide: { [apiKey as symbol]: client } } })
    await wrapper.get('input[type="checkbox"]').setValue(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(payload).toEqual({ expected_version: 2, is_active: false })
  })

  it('keeps an unsaved name when a separate qualification command succeeds', async () => {
    const qualified = { ...employee.specialties[1], status: 'qualified', version: 2 }
    const client = new ApiClient(async input => String(input).endsWith('/csrf/') ? json({ csrf_token: 'token' }) : json(qualified))
    const wrapper = mount(EmployeePanel, { props: { employee }, global: { plugins: [sessionWith('employees.update', 'specialties.qualify')], provide: { [apiKey as symbol]: client } } })
    await wrapper.get('input:not([type])').setValue('Имя в несохранённом черновике')
    await wrapper.get('[data-qualify="es-2"]').trigger('click')
    await wrapper.get('[name="qualified_at"]').setValue('2026-10-28')
    await wrapper.get('[name="qualification_basis"]').setValue('Протокол')
    await wrapper.get('[data-confirm-qualification]').trigger('submit')
    await flushPromises()
    const updated = wrapper.emitted('updated')![0]![0] as typeof employee
    await wrapper.setProps({ employee: updated })
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Имя в несохранённом черновике')
  })

  it('keeps the draft original version if a separate reload receives newer employee data', async () => {
    let payload: unknown
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      payload = JSON.parse(String(init?.body))
      return json({ code: 'version_conflict', message: 'Карточка изменена.', field_errors: {} }, 409)
    })
    const wrapper = mount(EmployeePanel, { props: { employee }, global: { plugins: [sessionWith('employees.update')], provide: { [apiKey as symbol]: client } } })
    await wrapper.get('input:not([type])').setValue('Черновик')
    await wrapper.setProps({ employee: { ...employee, full_name: 'Изменено другим сотрудником', version: 3 } })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(payload).toEqual({ expected_version: 2, full_name: 'Черновик' })
    expect(wrapper.get('[role="alert"]').text()).toContain('Конфликт')
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Черновик')
  })
})
