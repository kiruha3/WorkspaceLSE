import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })
describe('manual expertise registration', () => {
  it('registers with a stable UUID retry key when randomUUID is unavailable outside localhost', async () => {
    const getRandomValues = crypto.getRandomValues.bind(crypto)
    vi.stubGlobal('crypto', { randomUUID: undefined, getRandomValues })
    const keys: (string | null)[] = [], componentErrors: unknown[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/expertises/')) {
        keys.push(new Headers(init?.headers).get('Idempotency-Key'))
        if (keys.length < 3) throw new TypeError('Связь потеряна')
        return json(expertise, 201)
      }
      if (path.includes('number-hint')) return json({ last_number: null })
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      if (path.includes('/complex-groups/')) return json(page([]))
      return json(receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client }, config: { errorHandler: error => { componentErrors.push(error) } } } })
    try {
      await flushPromises()
      await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
      await wrapper.get('[name="specialty_id"]').setValue('s-18')
      await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
      expect(componentErrors).toEqual([])
      expect(keys).toHaveLength(1)
      expect(keys[0]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
      expect(wrapper.text()).toContain('Связь потеряна')
      await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
      expect(keys[1]).toBe(keys[0])
      await wrapper.get('[name="registration_number"]').setValue('152/4-1-26')
      await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
      expect(keys[2]).not.toBe(keys[0])
      expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    } finally { wrapper.unmount() }
  })
  it('keeps an amendment open when discarding its unsaved basis is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const client = new ApiClient(async input => String(input).includes('/references/') ? json(page([department])) : json(receipt))
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'receipts.amend', 'documents.upload'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    const toggle = wrapper.findAll('button').find(button => button.text() === 'Уточнить поступление')!
    await toggle.trigger('click')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[name="document_title"]').setValue('Несохранённый документ')
    await toggle.trigger('click')
    expect(wrapper.find('[name="document_title"]').exists()).toBe(true)
    expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Несохранённый документ')
    wrapper.unmount()
  })
  it('changes receipt cards without carrying the previous department or complex groups', async () => {
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department, { ...department, id: 'd-3', code: '3', name: 'Отдел 3' }] : [specialty]))
      if (path.includes('number-hint')) return json({ last_number: null })
      if (path.includes('/complex-groups/')) return json(page(path.includes('receipt-2') ? [] : [{ id: 'group-1', title: 'Чужая прежняя группа', material_id: receipt.material.id }]))
      return json(path.includes('receipt-2') ? { ...receipt, id: 'receipt-2', department_id: 'd-3' } : receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Чужая прежняя группа')
    await router.push('/receipts/receipt-2'); await flushPromises()
    expect((wrapper.get('[name="department_id"]').element as HTMLSelectElement).value).toBe('d-3')
    expect(wrapper.text()).not.toContain('Чужая прежняя группа')
    wrapper.unmount()
  })

  it('keeps a late number hint from replacing the selected department hint', async () => {
    let resolveOld!: (value: Response) => void
    const oldHint = new Promise<Response>(resolve => { resolveOld = resolve })
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department, { ...department, id: 'd-3', code: '3', name: 'Отдел 3' }] : [specialty]))
      if (path.includes('number-hint')) return path.includes('d-4') ? oldHint : json({ last_number: '40/3-2-26' })
      if (path.includes('/complex-groups/')) return json(page([]))
      return json(receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[name="department_id"]').setValue('d-3'); await flushPromises()
    resolveOld(json({ last_number: '150/4-1-26' })); await flushPromises()
    expect(wrapper.text()).toContain('40/3-2-26')
    expect(wrapper.text()).not.toContain('150/4-1-26')
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('')
    wrapper.unmount()
  })

  it('keeps entered registration data on a 403 and never presents a saved work', async () => {
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') return json({ code: 'permission_denied', message: 'Право регистрации отозвано', field_errors: {} }, 403)
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      if (path.includes('number-hint')) return json({ last_number: null })
      if (path.includes('/complex-groups/')) return json(page([]))
      return json(receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
    await wrapper.get('[name="specialty_id"]').setValue('s-18')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Право регистрации отозвано')
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('151/4-1-26')
    expect(wrapper.find('.message-success').exists()).toBe(false)
    expect(router.currentRoute.value.path).toBe('/receipts/receipt-1')
    wrapper.unmount()
  })
  it('preserves a prepared amendment document and entered reason while reloading the server receipt', async () => {
    let docWrites = 0
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/documents/') && init?.method === 'POST') { docWrites++; return json({ id: 'new-basis', kind: 'resolution', title: 'Новое основание', source_kind: 'paper_original', department_id: 'd-4', version: 1, versions: [] }, 201) }
      if (path.endsWith('/amend/')) return json({ code: 'version_conflict', message: 'Поступление изменилось', field_errors: {} }, 409)
      if (path.includes('/references/')) return json(page([department]))
      return json(receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'receipts.amend', 'documents.upload'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === 'Уточнить поступление')!.trigger('click')
    await wrapper.get('input[type="checkbox"]').setValue(true)
    await wrapper.get('[name="document_title"]').setValue('Новое основание')
    await wrapper.get('[name="amend_reason"]').setValue('Уточнено основание')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(docWrites).toBe(1)
    await wrapper.findAll('button').find(button => button.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
    expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Новое основание')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(docWrites).toBe(1)
    wrapper.unmount()
  })
  it('keeps the number manual, replays the same failed payload key and changes the key after an edit', async () => {
    const commands: { key: string | null; body: unknown }[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/expertises/')) {
        commands.push({ key: new Headers(init?.headers).get('Idempotency-Key'), body: JSON.parse(String(init?.body)) })
        if (commands.length < 3) throw new TypeError('Связь потеряна')
        return json(expertise, 201)
      }
      if (path.includes('number-hint')) return json({ last_number: '150/4-1-26' })
      if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
      if (path.includes('/complex-groups/')) return json(page([]))
      return json(receipt)
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).toContain('150/4-1-26')
    await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
    await wrapper.get('[name="specialty_id"]').setValue('s-18')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Связь потеряна')
    expect(router.currentRoute.value.path).toBe('/receipts/receipt-1')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(commands[0]?.key).toBeTruthy()
    expect(commands[1]?.key).toBe(commands[0]?.key)
    expect(commands[0]?.body).toEqual({ expected_version: 2, registration_number: '151/4-1-26', historical_number: '', department_id: 'd-4', specialty_id: 's-18', appointment_nature: 'primary', is_commission: false, complex_group_id: null })
    await wrapper.get('[name="registration_number"]').setValue('152/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(commands[2]?.key).not.toBe(commands[0]?.key)
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    wrapper.unmount()
  })

  it('accepts an intake separately from assigning a manual expertise number', async () => {
    const commands: string[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { commands.push(path); return json(receipt) }
      return json({ ...receipt, status: 'draft' })
    })
    const router = await testRouter('/receipts/receipt-1')
    const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'receipts.accept'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.find('[name="registration_number"]').exists()).toBe(false)
    await wrapper.get('[data-accept-receipt]').trigger('click'); await flushPromises()
    expect(commands).toEqual(['/api/v1/receipts/receipt-1/register/'])
    expect(wrapper.text()).toContain('Принято')
    wrapper.unmount()
  })
})
