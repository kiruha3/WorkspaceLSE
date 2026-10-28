import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { ApiClient, apiKey } from '../../api/client'
import { json, sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
import ReconciliationPage from './ReconciliationPage.vue'
import { router as applicationRouter } from '../../router'

const department = { id: 'department-4', code: '4', name: 'Отдел4', is_active: true }
const specialty = { id: 'specialty-18', code: '18.1', name: 'Специальность18.1', is_active: true }
const row = { id: 'row-1', source_row: 4, raw: { B: '151/4-1-26' }, formulas: {}, extra: {}, facts: { registration_number: '151/4-1-26', department_code: '4', specialty_code: '18.1', executor_raw: 'Имя в источнике', state: 'completed', questions: 2, categorical: 2, probable: 0, unresolved: 0 }, diagnostics: [], normalization_complete: true }
const selection = { id: 'selection-1', row_id: 'row-1', version: 3, department_id: department.id, specialty_id: specialty.id, employee_ids: [], appointment_nature: null, is_commission: null, complex_known: false, complex_group_key: null, statistics_confirmed: false, reason: 'Подтверждено ранее' }
const item = { row, classification: 'new', existing_work: null, blockers: [], suggested_department: department, suggested_specialty: specialty, selection: null }
const summary = { new: 2, changed: 0, unchanged: 0, invalid: 1 }
const options = { departments: [department], specialties: [specialty], employees: [{ id: 'employee-1', full_name: 'Эксперт истории', is_active: true }] }
const application = { id: 'application-1', batch_id: 'batch-1', created_at: '2026-10-28T00:00:00Z', created_count: 1, existing_count: 0, items: [{ row_id: 'row-1', expertise_id: 'real-work-1', action: 'created' }] }
const resultPage = (saved = false) => ({ count: 1, next: null, previous: null, results: [{ ...item, selection: saved ? selection : null }], summary, batch_id: 'batch-1' })
type Transport = ConstructorParameters<typeof ApiClient>[0]
async function open({ url = '/imports/batch-1/reconciliation', saved = false, codes = ['imports.results.view', 'imports.reconcile', 'imports.apply'], capability = true, transport }: { url?: string; saved?: boolean; codes?: string[]; capability?: boolean; transport?: Transport } = {}) {
  const pinia = sessionWith(...codes)
  useSessionStore(pinia).user!.supported_modules = capability ? ['journal_import_preview', 'journal_application'] : ['journal_import_preview']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/imports/:id/reconciliation', component: ReconciliationPage }, { path: '/imports/:id', component: { template: '<p>Снимок</p>' } }, { path: '/expertises/:id', component: { template: '<p>Рабочая экспертиза</p>' } }] })
  await router.push(url)
  const client = new ApiClient(transport ?? (async input => json(String(input).includes('reconciliation-options') ? options : resultPage(saved))))
  const wrapper = mount(RouterView, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  return { wrapper, router, pinia }
}
enableAutoUnmount(afterEach)
afterEach(() => vi.restoreAllMocks())

it('keeps factual department1 instead of substituting a modern staff department4',async()=>{
  const oldDepartment={id:'department-1',code:'1',name:'Исторический отдел1',is_active:false}
  const oldItem={...item,row:{...row,raw:{B:'151/1-1-26'},facts:{...row.facts,registration_number:'151/1-1-26',department_code:'1'}},suggested_department:oldDepartment,mapped_department:null}
  const writes:unknown[]=[]
  const {wrapper}=await open({transport:async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'t'})
    if(init?.method==='PUT'){writes.push(JSON.parse(String(init.body)));return json({event:{id:'e'},selection:{...selection,department_id:'department-1',version:1}})}
    return json(path.includes('options')?{...options,departments:[oldDepartment,department]}:{...resultPage(),results:[oldItem]})
  }})
  expect(wrapper.text()).toContain('Отдел номера: 1')
  await wrapper.get('[data-edit-selection]').trigger('click');await flushPromises()
  expect(wrapper.get('[name="selection_department"]').element).toHaveProperty('value','department-1')
  expect(wrapper.find('[name="selection_department"] option[value="department-4"]').exists()).toBe(false)
  await wrapper.get('[name="selection_reason"]').setValue('Фактический отдел1 сохраняется')
  await wrapper.get('[data-selection-form]').trigger('submit');await flushPromises()
  expect(writes[0]).toMatchObject({department_id:'department-1'})
  expect(wrapper.text()).toContain('151/1-1-26')
  expect(wrapper.get('[data-mapped-department]').text()).toContain('1 · Исторический отдел1')
})

it('shows factual mapped department to a source reader without personnel options',async()=>{
  const oldDepartment={id:'department-1',code:'1',name:'Исторический отдел1',is_active:false}
  const {wrapper}=await open({codes:['imports.results.view'],transport:async()=>json({...resultPage(true),results:[{...item,selection:{...selection,department_id:'department-1'},mapped_department:oldDepartment,row:{...row,raw:{B:'151/1-1-26'},facts:{...row.facts,registration_number:'151/1-1-26',department_code:'1'}}}]})})
  expect(wrapper.get('[data-mapped-department]').text()).toContain('1 · Исторический отдел1')
  expect(wrapper.text()).toContain('Отдел номера: 1')
  expect(wrapper.find('[data-edit-selection]').exists()).toBe(false)
})

describe('confirmed journal reconciliation', () => {
  it('lets an allowed reader reopen the existing work after the protocol page was reloaded', async () => {
    const { wrapper } = await open({ codes:['imports.results.view','expertise.view'],transport:async()=>json({...resultPage(),results:[{...item,classification:'unchanged',existing_work:{id:'existing-work',registration_number:'151/4-1-26',version:1}}]}) })
    expect(wrapper.get('[data-existing-work]').attributes('href')).toContain('/expertises/existing-work')
    expect(wrapper.get('[data-existing-work]').text()).toContain('151/4-1-26')
  })
  it('registers the actual source reconciliation URL with read and server support gates', () => {
    const resolved = applicationRouter.resolve('/imports/batch-1/reconciliation')
    expect(resolved.meta.permission).toBe('imports.results.view')
    expect(resolved.meta.supportedModule).toBe('journal_application')
  })
  it('keeps global counts and URL filters separate from the displayed page', async () => {
    const paths: string[] = []
    const { wrapper, router } = await open({ url: '/imports/batch-1/reconciliation?classification=new&search=151&page=2', transport: async input => { paths.push(String(input)); return json(String(input).includes('options') ? options : { ...resultPage(), previous: '?page=1' }) } })
    expect(paths.some(path => path.includes('classification=new') && path.includes('search=151') && path.includes('page=2'))).toBe(true)
    expect(wrapper.get('[data-reconciliation-summary]').text()).toContain('Новые: 2')
    expect(wrapper.get('[data-reconciliation-summary]').text()).toContain('Нужна проверка: 1')
    await wrapper.get('[name="search"]').setValue('152'); await wrapper.get('form.toolbar').trigger('submit'); await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ classification: 'new', search: '152', page: '1' })
  })

  it('does not request or advertise application without the server module', async () => {
    const paths: string[] = []
    const { wrapper } = await open({ capability: false, transport: async input => { paths.push(String(input)); return json(resultPage()) } })
    expect(paths).toEqual([])
    expect(wrapper.find('[data-apply-import]').exists()).toBe(false)
    expect(wrapper.find('[data-edit-selection]').exists()).toBe(false)
  })

  it('allows a source reader to inspect classification without loading employee options or editing', async () => {
    const paths: string[] = []
    const { wrapper } = await open({ codes: ['imports.results.view'], transport: async input => { paths.push(String(input)); return json(resultPage()) } })
    expect(wrapper.text()).toContain('151/4-1-26')
    expect(paths.some(path => path.includes('options'))).toBe(false)
    expect(wrapper.find('[data-edit-selection]').exists()).toBe(false)
    expect(wrapper.find('[data-select-application-row]').exists()).toBe(false)
  })

  it('saves only explicit mappings, null unknowns and the current selection version', async () => {
    const writes: { path: string; body: unknown; key: string | null }[] = []
    const { wrapper } = await open({ transport: async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'PUT') { writes.push({ path, body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ event: { id: 'event-1' }, selection: { ...selection, version: 1, reason: 'Проверил строку' } }) }
      return json(path.includes('options') ? options : resultPage())
    } })
    await wrapper.get('[data-edit-selection]').trigger('click'); await flushPromises()
    expect(wrapper.get('[name="selection_nature"]').element).toHaveProperty('value', '')
    expect(wrapper.get('[name="selection_commission"]').element).toHaveProperty('value', '')
    await wrapper.get('[name="selection_reason"]').setValue('  Проверил строку  ')
    await wrapper.get('[data-selection-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1); expect(writes[0]!.key).toBeTruthy()
    expect(writes[0]!.path).toBe('/api/v1/imports/batch-1/rows/row-1/selection/')
    expect(writes[0]!.body).toEqual({ expected_version: 0, reason: 'Проверил строку', department_id: 'department-4', specialty_id: 'specialty-18', employee_ids: [], appointment_nature: null, is_commission: null, complex_known: false, complex_group_key: null, statistics_confirmed: false })
    expect(wrapper.get('[data-select-application-row]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-selection-form]').exists()).toBe(false)
  })

  it('retries a lost selection response with the exact original body and key', async () => {
    const writes: { body: unknown; key: string | null }[] = []
    const { wrapper } = await open({ transport: async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'PUT') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) throw new TypeError('Ответ потерян'); return json({ event: { id: 'event-1' }, selection: { ...selection, version: 1 } }) }
      return json(String(input).includes('options') ? options : resultPage())
    } })
    await wrapper.get('[data-edit-selection]').trigger('click'); await flushPromises()
    await wrapper.get('[name="selection_reason"]').setValue('Подтвердить перенос')
    await wrapper.get('[data-selection-form]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-selection-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0])
  })

  it('applies only saved row IDs with approved versions and displays actual work links', async () => {
    const writes: { body: unknown; key: string | null }[] = []
    const { wrapper } = await open({ saved: true, transport: async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ event: { id: 'apply-event' }, application }, 201) }
      return json(String(input).includes('options') ? options : resultPage(true))
    } })
    await wrapper.get('[data-select-application-row]').setValue(true)
    await wrapper.get('[name="application_reason"]').setValue('  Подтверждаю пакет  ')
    await wrapper.get('[data-application-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(1); expect(writes[0]!.key).toBeTruthy()
    expect(writes[0]!.body).toEqual({ reason: 'Подтверждаю пакет', selections: [{ row_id: 'row-1', expected_selection_version: 3 }] })
    expect(wrapper.get('[data-application-result]').text()).toContain('Создано: 1')
    expect(wrapper.get('[data-applied-work]').attributes('href')).toContain('/expertises/real-work-1')
    expect(wrapper.get('[data-applied-work]').text()).toContain('151/4-1-26')
  })

  it.each([403, 409])('retains the explicit packet after managed server %s, without reporting success', async status => {
    const { wrapper } = await open({ saved: true, transport: async (input, init) => String(input).endsWith('/csrf/') ? json({ csrf_token: 'token' }) : init?.method === 'POST' ? json({ code: 'command_conflict', message: 'Пакет не применён', field_errors: {} }, status) : json(String(input).includes('options') ? options : resultPage(true)) })
    await wrapper.get('[data-select-application-row]').setValue(true)
    await wrapper.get('[name="application_reason"]').setValue('Обоснование пакета')
    await wrapper.get('[data-application-form]').trigger('submit'); await flushPromises()
    expect(wrapper.get('[name="application_reason"]').element).toHaveProperty('value', 'Обоснование пакета')
    expect(wrapper.text()).toContain('Пакет не применён')
    expect(wrapper.find('[data-application-result]').exists()).toBe(false)
  })

  it('guards unsaved reconciliation when leaving is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper, router } = await open()
    await wrapper.get('[data-edit-selection]').trigger('click'); await flushPromises()
    await wrapper.get('[name="selection_reason"]').setValue('Не сохранено')
    await router.push('/imports/batch-2/reconciliation'); await flushPromises()
    expect(router.currentRoute.value.params.id).toBe('batch-1')
    expect(wrapper.get('[name="selection_reason"]').element).toHaveProperty('value', 'Не сохранено')
  })

  it('discards the old source reply after navigating to another snapshot', async () => {
    let resolveOld!: (value: Response) => void
    const old = new Promise<Response>(resolve => { resolveOld = resolve })
    const { wrapper, router } = await open({ transport: async input => String(input).includes('options') ? json(options) : String(input).includes('batch-1') ? old : json({ ...resultPage(), batch_id: 'batch-2', results: [{ ...item, row: { ...row, facts: { ...row.facts, registration_number: 'Новое поступление' } } }] }) })
    await router.push('/imports/batch-2/reconciliation'); await flushPromises()
    expect(wrapper.text()).toContain('Новое поступление')
    resolveOld(json(resultPage())); await flushPromises()
    expect(wrapper.text()).not.toContain('151/4-1-26')
    expect(wrapper.text()).toContain('Новое поступление')
  })

  it('does not discard an unsaved mapping on a declined manual refresh', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { wrapper } = await open()
    await wrapper.get('[data-edit-selection]').trigger('click'); await flushPromises()
    await wrapper.get('[name="selection_reason"]').setValue('Сохранить мой ввод')
    await wrapper.findAll('button').find(button => button.text() === 'Обновить сверку')!.trigger('click'); await flushPromises()
    expect(wrapper.get('[name="selection_reason"]').element).toHaveProperty('value', 'Сохранить мой ввод')
  })

  it('does not save an unnamed complex as a confirmed noncomplex work', async () => {
    const { wrapper } = await open()
    await wrapper.get('[data-edit-selection]').trigger('click'); await flushPromises()
    await wrapper.get('[name="selection_reason"]').setValue('Состав проверен')
    await wrapper.get('[name="selection_complex"]').setValue('group')
    expect(wrapper.get('[data-selection-form] button').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="selection_group"]').setValue('complex-a')
    expect(wrapper.get('[data-selection-form] button').attributes('disabled')).toBeUndefined()
  })

  it('retries an uncertain application with the same approved versions and key', async () => {
    const writes: { body: unknown; key: string | null }[] = []
    const { wrapper } = await open({ saved: true, transport: async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) throw new TypeError('Потерян ответ'); return json({ event: { id: 'event' }, application }, 201) }
      return json(String(input).includes('options') ? options : resultPage(true))
    } })
    await wrapper.get('[data-select-application-row]').setValue(true)
    await wrapper.get('[name="application_reason"]').setValue('Подтверждённый пакет')
    await wrapper.get('[data-application-form]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-application-form]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0])
    expect(wrapper.find('[data-application-result]').exists()).toBe(true)
  })
})
