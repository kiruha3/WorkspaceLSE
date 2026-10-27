import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import { expertise } from '../../test/intakeFixtures'
import AssignmentForm from './AssignmentForm.vue'

describe('qualified assignment', () => {
  it('shows candidate reasons, requires two commission participants and retains selection on a server recheck conflict', async () => {
    const writes: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ code: 'version_conflict', message: 'Квалификация изменилась', field_errors: { employee_ids: ['Проверьте состав'] } }, 409) }
      return json([{ id: 'e-1', full_name: 'Эксперт первый', eligible: true, code: 'qualified', message: 'Допущен' }, { id: 'e-2', full_name: 'Эксперт второй', eligible: true, code: 'qualified', message: 'Допущен' }, { id: 'e-3', full_name: 'Стажёр', eligible: false, code: 'training', message: 'Обучение по 18.1' }])
    })
    const wrapper = mount(AssignmentForm, { props: { expertise: { ...expertise, is_commission: true }, action: 'assign' }, global: { plugins: [sessionWith('expertise.assign')], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.get('[value="e-3"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Обучение по 18.1')
    await wrapper.get('[value="e-1"]').setValue(true)
    await wrapper.get('[name="assignment_reason"]').setValue('Резолюция начальника')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    await wrapper.get('[value="e-2"]').setValue(true)
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, employee_ids: ['e-1', 'e-2'], reason: 'Резолюция начальника' }])
    expect(wrapper.get('[value="e-1"]').element).toHaveProperty('checked', true)
    expect(wrapper.text()).toContain('Квалификация изменилась')
    expect(wrapper.emitted('updated')).toBeUndefined()
    wrapper.unmount()
  })
})
