import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { employee, json, page, sessionWith } from '../../test/fixtures'
import EmployeeOrganization from './EmployeeOrganization.vue'

describe('employee organization assignments', () => {
  it('adds an explicit department and position with the known dates and reason', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ path, body: JSON.parse(String(init.body)) }); return json(employee.org_assignments[0], 201) }
      return path.includes('/departments/') ? json(page([{ id: 'd-4', code: '4', name: 'Отдел 4', is_active: true, version: 1 }])) : json(page([{ id: 'p-1', code: 'expert', name: 'Эксперт', is_active: true, version: 1 }]))
    })
    const wrapper = mount(EmployeeOrganization, { props: { employeeId: 'employee-1', assignments: [] }, global: { plugins: [sessionWith('employees.org_assignments.manage')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-add-org]').exists()).toBe(true)
    await wrapper.get('[data-add-org]').trigger('click')
    await wrapper.get('[name="org_department"]').setValue('d-4')
    await wrapper.get('[name="org_position"]').setValue('p-1')
    await wrapper.get('[name="org_valid_from"]').setValue('2026-10-28')
    await wrapper.get('[name="org_reason"]').setValue('Кадровый приказ')
    await wrapper.get('[data-org-create-form]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/employees/employee-1/org-assignments/', body: { department_id: 'd-4', position_id: 'p-1', valid_from: '2026-10-28', valid_to: null, reason: 'Кадровый приказ' } }])
    expect(wrapper.emitted('updated')?.[0]?.[0]).toMatchObject({ id: 'org-1', version: 1 })
  })

  it('ends a specific organization assignment with its expected version', async () => {
    let write: unknown
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'PATCH') { write = { path: String(input), body: JSON.parse(String(init.body)) }; return json({ ...employee.org_assignments[0], valid_to: '2026-10-28', version: 2 }) }
      return json(page([]))
    })
    const wrapper = mount(EmployeeOrganization, { props: { employeeId: 'employee-1', assignments: employee.org_assignments }, global: { plugins: [sessionWith('employees.org_assignments.manage')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[data-end-org="org-1"]').exists()).toBe(true)
    await wrapper.get('[data-end-org="org-1"]').trigger('click')
    await wrapper.get('[name="org_end_date"]').setValue('2026-10-28')
    await wrapper.get('[name="org_end_reason"]').setValue('Перевод')
    await wrapper.get('[data-org-end-form]').trigger('submit')
    await flushPromises()
    expect(write).toEqual({ path: '/api/v1/employee-org-assignments/org-1/', body: { expected_version: 1, valid_to: '2026-10-28', reason: 'Перевод' } })
  })
})
