import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import { expertise, testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'
afterEach(() => vi.restoreAllMocks())

describe('persisted work card', () => {
  it('shows the separate linked numbers of a complex expertise', async () => {
    const work = { ...expertise, complex_group: { id: 'complex-internal', title: '', expertises: [{ id: expertise.id, registration_number: expertise.registration_number }, { id: 'work-2', registration_number: '152/3-1-26' }] } }
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: new ApiClient(async () => json(work)) } } })
    await flushPromises()
    expect(wrapper.get('[data-complex-numbers]').text()).toContain(expertise.registration_number)
    expect(wrapper.get('[data-complex-numbers]').text()).toContain('152/3-1-26')
    expect(wrapper.get('[data-complex-numbers] a[href^="/expertises/work-2"]').attributes('href')).toContain('/expertises/work-2')
    expect(wrapper.get('[data-complex-numbers]').text()).not.toContain('complex-internal')
    wrapper.unmount()
  })
  it('returns to the personal workplace when opened from its missing-data list', async () => {
    const router = await testRouter('/expertises/work-1?return=%2Fworkspace')
    router.addRoute({ path: '/workspace', component: { template: '<div>Рабочее место</div>' } })
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: new ApiClient(async () => json(expertise)) } } })
    await flushPromises()
    expect(wrapper.get('[data-back-to-expertises]').attributes('href')).toBe('/workspace')
    expect(wrapper.get('[data-back-to-expertises]').text()).toContain('личному кабинету')
    wrapper.unmount()
  })
  it('clearly marks training work excluded from the registry report',async()=>{
    const client=new ApiClient(async()=>json({...expertise,material:{...expertise.material,is_demo:true}}))
    const router=await testRouter('/expertises/work-1')
    const wrapper=mount(ExpertisePage,{global:{plugins:[sessionWith('expertise.view'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises();expect(wrapper.text()).toContain('Учебный материал');wrapper.unmount()
  })
  it('does not let a late detail reload overwrite a confirmed assignment', async () => {
    let readCount = 0, resolveOld!: (value: Response) => void
    const oldRead = new Promise<Response>(resolve => { resolveOld = resolve })
    const assigned = { ...expertise, version: 2, allowed_actions: ['expertise.reassign'], current_assignments: [{ id: 'a-1', employee: { id: 'e-1', full_name: 'Эксперт первый' }, started_at: '2026-10-28T08:00:00Z', ended_at: null, reason: 'Резолюция' }] }
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.includes('assignment-candidates')) return json([{ id: 'e-1', full_name: 'Эксперт первый', eligible: true, code: 'qualified', message: 'Допущен' }])
      if (init?.method === 'POST') return json(assigned)
      readCount++; return readCount === 1 ? json(expertise) : oldRead
    })
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.assign'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises(); await wrapper.get('[data-card-tab="assignments"]').trigger('click'); await wrapper.get('[data-start-assignment]').trigger('click'); await flushPromises()
    await wrapper.get('[value="e-1"]').setValue(true)
    await wrapper.get('[name="assignment_reason"]').setValue('Резолюция')
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.get('[data-current-assignments]').text()).toContain('Эксперт первый')
    resolveOld(json(expertise)); await flushPromises()
    expect(wrapper.get('[data-current-assignments]').text()).toContain('Эксперт первый')
    expect(wrapper.text()).toContain('Версия работы 2')
    wrapper.unmount()
  })

  it('clears an abandoned assignment when navigating to another work after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const client = new ApiClient(async input => String(input).includes('assignment-candidates') ? json([{ id: 'e-1', full_name: 'Эксперт первый', eligible: true, code: 'qualified', message: 'Допущен' }]) : json({ ...expertise, id: String(input).includes('work-2') ? 'work-2' : 'work-1' }))
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.assign'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises(); await wrapper.get('[data-card-tab="assignments"]').trigger('click'); await wrapper.get('[data-start-assignment]').trigger('click'); await flushPromises()
    await wrapper.get('[name="assignment_reason"]').setValue('Не для новой работы')
    await router.push('/expertises/work-2'); await flushPromises()
    expect(wrapper.find('[name="assignment_reason"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('refreshes a conflicted version without destroying an unsaved assignment form', async () => {
    let version = 1
    const client = new ApiClient(async input => {
      if (String(input).includes('assignment-candidates')) return json([{ id: 'e-1', full_name: 'Эксперт первый', eligible: true, code: 'qualified', message: 'Допущен' }])
      return json({ ...expertise, version })
    })
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.assign'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises(); await wrapper.get('[data-card-tab="assignments"]').trigger('click'); await wrapper.get('[data-start-assignment]').trigger('click'); await flushPromises()
    await wrapper.get('[value="e-1"]').setValue(true)
    await wrapper.get('[name="assignment_reason"]').setValue('Несохранённое основание')
    version = 2
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    expect((wrapper.get('[name="assignment_reason"]').element as HTMLTextAreaElement).value).toBe('Несохранённое основание')
    expect(wrapper.get('[value="e-1"]').element).toHaveProperty('checked', true)
    expect(wrapper.text()).toContain('Версия работы 2')
    wrapper.unmount()
  })
  it('uses card actions instead of a broad session grant and keeps historical assignments separate', async () => {
    const client = new ApiClient(async () => json({ ...expertise, allowed_actions: [], current_assignments: [{ id: 'a-2', employee: { id: 'e-2', full_name: 'Новый эксперт' }, started_at: '2026-10-28T08:00:00Z', ended_at: null, reason: 'Перепоручение' }], assignment_history: [{ id: 'a-1', employee: { id: 'e-1', full_name: 'Прежний эксперт' }, started_at: '2026-10-27T08:00:00Z', ended_at: '2026-10-28T08:00:00Z', reason: 'Первое назначение' }], basis_document: { id: 'secret', restricted: true } }))
    const router = await testRouter('/expertises/work-1?return=%2Fexpertises%3Fpage%3D2')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.assign', 'expertise.reassign'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.get('[data-current-assignments]').text()).toContain('Новый эксперт')
    expect(wrapper.get('[data-current-assignments]').text()).not.toContain('Прежний эксперт')
    expect(wrapper.get('[data-assignment-history]').text()).toContain('Прежний эксперт')
    expect(wrapper.find('[data-start-assignment]').exists()).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.text()).toContain('Доступ к документу ограничен')
    expect(wrapper.get('[data-back-to-expertises]').attributes('href')).toBe('/expertises?page=2')
    wrapper.unmount()
  })
})
