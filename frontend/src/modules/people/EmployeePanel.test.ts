import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { apiKey, ApiClient } from '../../api/client'
import { employee, json, sessionWith } from '../../test/fixtures'
import EmployeePanel from './EmployeePanel.vue'

describe('employee edits', () => {
  it('sends only a changed name, not an unchanged deactivation field from another action', async () => {
    let payload: unknown
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({csrf_token:'token'})
      payload = JSON.parse(String(init?.body))
      return json({...employee,full_name:'Новое имя',version:3})
    })
    const wrapper = mount(EmployeePanel,{props:{employee},global:{plugins:[sessionWith('employees.update','employees.deactivate')],provide:{[apiKey as symbol]:client}}})
    await wrapper.get('input:not([type])').setValue('Новое имя')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(payload).toEqual({expected_version:2,full_name:'Новое имя'})
    wrapper.unmount()
  })

  it('lets qualification explicitly correct a previously recorded expiry', async () => {
    const person = {...employee,specialties:employee.specialties.map(s=>({...s,valid_until:'2026-09-30'}))}
    let payload: unknown
    const client = new ApiClient(async (input,init)=>{
      if(String(input).endsWith('/csrf/')) return json({csrf_token:'token'})
      payload = JSON.parse(String(init?.body))
      return json({...person.specialties[1],status:'qualified',qualified_at:'2026-10-01',valid_until:'2027-10-01',version:2})
    })
    const wrapper = mount(EmployeePanel,{props:{employee:person},global:{plugins:[sessionWith('specialties.qualify')],provide:{[apiKey as symbol]:client}}})
    await wrapper.get('[data-qualify="es-2"]').trigger('click')
    expect((wrapper.get('[name="qualification_valid_until"]').element as HTMLInputElement).value).toBe('2026-09-30')
    await wrapper.get('[name="qualified_at"]').setValue('2026-10-01')
    await wrapper.get('[name="qualification_valid_until"]').setValue('2027-10-01')
    await wrapper.get('[name="qualification_basis"]').setValue('Новый документ')
    await wrapper.get('[data-confirm-qualification]').trigger('submit')
    await flushPromises()
    expect(payload).toEqual({expected_version:1,qualified_at:'2026-10-01',valid_until:'2027-10-01',basis:'Новый документ'})
    wrapper.unmount()
  })
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

  it('confirms qualification with an unknown date and a basis while retaining unsaved metadata', async () => {
    const qualified = { ...employee.specialties[1], status: 'qualified', qualified_at: null, basis: 'Подтверждено приказом', version: 2 }
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      writes.push(JSON.parse(String(init?.body)))
      return json(qualified)
    })
    const wrapper = mount(EmployeePanel, { props: { employee }, global: { plugins: [sessionWith('employees.update', 'specialties.qualify')], provide: { [apiKey as symbol]: client } } })
    await wrapper.get('input:not([type])').setValue('Несохранённое имя')
    await wrapper.get('[data-qualify="es-2"]').trigger('click')
    await wrapper.get('[name="qualification_basis"]').setValue('Подтверждено приказом')
    const form = wrapper.get('[data-confirm-qualification]')
    expect((form.get('button.button-primary').element as HTMLButtonElement).disabled).toBe(false)
    expect((wrapper.get('[name="qualified_at"]').element as HTMLInputElement).required).toBe(false)
    await form.trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, qualified_at: null, basis: 'Подтверждено приказом' }])
    const updated = wrapper.emitted('updated')![0]![0] as typeof employee
    await wrapper.setProps({ employee: updated })
    expect((wrapper.get('input:not([type])').element as HTMLInputElement).value).toBe('Несохранённое имя')
    expect(wrapper.get('[role="status"]').text()).toContain('Квалификация подтверждена')
    wrapper.unmount()
  })

  it('does not confirm a qualification without a nonblank basis', async () => {
    let requests = 0
    const client = new ApiClient(async () => { requests++; return json({ csrf_token: 'token' }) })
    const wrapper = mount(EmployeePanel, { props: { employee }, global: { plugins: [sessionWith('specialties.qualify')], provide: { [apiKey as symbol]: client } } })
    await wrapper.get('[data-qualify="es-2"]').trigger('click')
    await wrapper.get('[name="qualification_basis"]').setValue('   ')
    await wrapper.get('[data-confirm-qualification]').trigger('submit')
    await flushPromises()
    expect(requests).toBe(0)
    expect(wrapper.find('[data-confirm-qualification]').exists()).toBe(true)
    wrapper.unmount()
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
