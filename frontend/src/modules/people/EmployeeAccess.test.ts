import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, role, sessionWith } from '../../test/fixtures'
import EmployeeAccess from './EmployeeAccess.vue'

describe('employee role assignments', () => {
  it('assigns departments for a mixed role without narrowing its institution-wide actions', async()=>{
    let payload: unknown
    const mixed = {...role,permissions:[{permission_code:'employees.view',scope:'institution'},{permission_code:'employees.update',scope:'departments'}]}
    const client = new ApiClient(async(input,init)=>{
      const path=String(input)
      if(path.endsWith('/csrf/')) return json({csrf_token:'token'})
      if(init?.method==='POST'){payload=JSON.parse(String(init.body));return json({id:'a-new',role:{id:role.id,name:role.name},scope_limit:'institution',department_ids:['d-4'],valid_from:null,valid_to:null,is_active:true,reason:'Совмещение',version:1})}
      if(path.includes('/references/')) return json(page([{id:'d-4',code:'4',name:'Отдел 4',is_active:true,version:1}]))
      if(path.includes('/employees/')) return json([])
      return json(page([mixed]))
    })
    const wrapper=mount(EmployeeAccess,{props:{employeeId:'employee-1'},global:{plugins:[sessionWith('access.roles.assign')],provide:{[apiKey as symbol]:client}}})
    await flushPromises()
    await wrapper.get('[name="assignment_role"]').setValue('role-1')
    await wrapper.get('[name="scope_limit"]').setValue('institution')
    expect(wrapper.find('[name="assignment_department"]').exists()).toBe(true)
    await wrapper.get('[name="assignment_department"]').setValue(['d-4'])
    await wrapper.get('[name="assignment_reason"]').setValue('Совмещение')
    await wrapper.get('[data-assign-role]').trigger('submit')
    await flushPromises()
    expect(payload).toEqual({role_id:'role-1',scope_limit:'institution',department_ids:['d-4'],valid_from:null,valid_to:null,reason:'Совмещение'})
    wrapper.unmount()
  })
  it('keeps multiple roles and assigns an explicit department limit with a reason', async () => {
    const assignments = [
      { id: 'a-1', role: { id: 'head', name: 'Руководитель отдела' }, scope_limit: 'departments', department_ids: ['d-4'], valid_from: null, valid_to: null, is_active: true, reason: 'Назначение', version: 1 },
      { id: 'a-2', role: { id: 'expert', name: 'Эксперт' }, scope_limit: 'own', department_ids: [], valid_from: null, valid_to: null, is_active: true, reason: 'Совмещение', version: 1 },
    ]
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ ...assignments[0], id: 'a-3', role: { id: role.id, name: role.name } }, 201) }
      if (path.includes('/references/departments/')) return json(page([{ id: 'd-4', code: '4', name: 'Отдел 4', is_active: true, version: 1 }]))
      if (path.includes('/employees/')) return json(assignments)
      return json(page([role]))
    })
    const wrapper = mount(EmployeeAccess, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('access.roles.view', 'access.roles.assign')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.findAll('[data-assignment]')).toHaveLength(2)
    expect(wrapper.text()).toContain('Руководитель отдела')
    expect(wrapper.text()).toContain('Эксперт')
    await wrapper.get('[name="assignment_role"]').setValue('role-1')
    await wrapper.get('[name="scope_limit"]').setValue('departments')
    await wrapper.get('[name="assignment_department"]').setValue(['d-4'])
    await wrapper.get('[name="assignment_reason"]').setValue('Совмещение обязанностей')
    await wrapper.get('[data-assign-role]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ role_id: 'role-1', scope_limit: 'departments', department_ids: ['d-4'], valid_from: null, valid_to: null, reason: 'Совмещение обязанностей' }])
  })

  it('refuses to send an empty department limit that could be mistaken for institution access', async () => {
    let posts = 0
    const client = new ApiClient(async (input, init) => {
      if (init?.method === 'POST') posts++
      if (String(input).includes('/employees/')) return json([])
      if (String(input).includes('/references/')) return json(page([{ id: 'd-4', code: '4', name: 'Отдел 4', is_active: true, version: 1 }]))
      return json(page([role]))
    })
    const wrapper = mount(EmployeeAccess, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('access.roles.assign')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-assign-role]').exists()).toBe(true)
    await wrapper.get('[name="assignment_role"]').setValue('role-1')
    await wrapper.get('[name="scope_limit"]').setValue('departments')
    await wrapper.get('[name="assignment_reason"]').setValue('Основание')
    await wrapper.get('[data-assign-role]').trigger('submit')
    await flushPromises()
    expect(posts).toBe(0)
    expect(wrapper.get('[role="alert"]').text()).toContain('Выберите хотя бы один отдел')
  })

  it('ends only the chosen role using its version and an explicit reason', async () => {
    const assignment = { id: 'a-1', role: { id: 'head', name: 'Руководитель отдела' }, scope_limit: 'departments', department_ids: ['d-4'], valid_from: null, valid_to: null, is_active: true, reason: 'Приказ', version: 3 }
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'PATCH') { writes.push({ path: String(input), body: JSON.parse(String(init.body)) }); return json({ ...assignment, is_active: false, version: 4 }) }
      if (String(input).includes('/employees/')) return json([assignment])
      return json(page([]))
    })
    const wrapper = mount(EmployeeAccess, { props: { employeeId: 'employee-1' }, global: { plugins: [sessionWith('access.roles.view', 'access.roles.assign')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-end-role="a-1"]').exists()).toBe(true)
    await wrapper.get('[data-end-role="a-1"]').trigger('click')
    await wrapper.get('[name="role_end_reason"]').setValue('Завершение замещения')
    await wrapper.get('[data-end-role-form]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/employee-roles/a-1/', body: { expected_version: 3, is_active: false, reason: 'Завершение замещения' } }])
    expect(wrapper.get('[data-assignment]').text()).toContain('Назначение прекращено')
  })
})
