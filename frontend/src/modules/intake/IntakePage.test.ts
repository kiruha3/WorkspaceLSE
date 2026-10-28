import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { basis, department, receipt, testRouter } from '../../test/intakeFixtures'
import IntakePage from './IntakePage.vue'

describe('intake creation', () => {
  it('sends an explicit training flag only when selected', async () => {
    let body:Record<string,unknown>|undefined
    const client=new ApiClient(async(input,init)=>{
      const path=String(input)
      if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
      if(path.endsWith('/receipts/')&&init?.method==='POST'){body=JSON.parse(String(init.body));return json(receipt,201)}
      return json(page(path.includes('/references/')?[department]:[]))
    })
    const router=await testRouter('/intake')
    const wrapper=mount(IntakePage,{global:{plugins:[sessionWith('receipts.view','receipts.create'),router],provide:{[apiKey as symbol]:client}}})
    await flushPromises();await wrapper.get('[data-new-receipt]').trigger('click')
    await wrapper.get('[name="received_at"]').setValue('2026-10-28');await wrapper.get('[name="department_id"]').setValue('d-4')
    await wrapper.get('[name="is_demo"]').setValue(true);await wrapper.get('form[data-create-receipt]').trigger('submit');await flushPromises()
    expect(body?.is_demo).toBe(true);wrapper.unmount()
  })
  it('persists a paper original without an invented file before creating the receipt', async () => {
    const writes: { path: string; body: unknown }[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ path, body: JSON.parse(String(init.body)) }); return json(path.endsWith('/documents/') ? basis : receipt, 201) }
      return json(page(path.includes('/references/') ? [department] : []))
    })
    const router = await testRouter('/intake')
    const wrapper = mount(IntakePage, { global: { plugins: [sessionWith('receipts.view', 'receipts.create', 'documents.upload'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    await wrapper.get('[data-new-receipt]').trigger('click')
    await wrapper.get('[name="received_at"]').setValue('2026-10-28')
    await wrapper.get('[name="material_title"]').setValue('Материалы дела')
    await wrapper.get('[name="department_id"]').setValue('d-4')
    await wrapper.get('[name="document_title"]').setValue('Постановление суда')
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    await wrapper.get('[data-create-receipt]').trigger('submit')
    await flushPromises()
    expect(writes).toEqual([
      { path: '/api/v1/documents/', body: { kind: 'resolution', title: 'Постановление суда', source_kind: 'paper_original', department_id: 'd-4' } },
      { path: '/api/v1/receipts/', body: { received_at: '2026-10-28', sender_name: '', material_title: 'Материалы дела', department_id: 'd-4', basis_document_id: 'document-1' } },
    ])
    expect(router.currentRoute.value.path).toBe('/receipts/receipt-1')
    wrapper.unmount()
  })

  it('keeps a prepared copy and form after failed upload and never claims a receipt was created', async () => {
    let documentWrites = 0, receiptWrites = 0, uploads = 0
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/documents/') && init?.method === 'POST') { documentWrites++; return json({ ...basis, source_kind: 'uploaded_copy' }, 201) }
      if (path.endsWith('/versions/')) { uploads++; return json({ code: 'upload_failed', message: 'Файл не сохранён', field_errors: { file: ['Повторите загрузку'] } }, 400) }
      if (path.endsWith('/receipts/') && init?.method === 'POST') { receiptWrites++; return json(receipt, 201) }
      return json(page(path.includes('/references/') ? [department] : []))
    })
    const router = await testRouter('/intake')
    const wrapper = mount(IntakePage, { global: { plugins: [sessionWith('receipts.view', 'receipts.create', 'documents.upload'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises(); await wrapper.get('[data-new-receipt]').trigger('click')
    await wrapper.get('[name="received_at"]').setValue('2026-10-28')
    await wrapper.get('[name="department_id"]').setValue('d-4')
    await wrapper.get('[name="document_title"]').setValue('Копия основания')
    await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
    Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'basis.pdf', { type: 'application/pdf' })] })
    await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-create-receipt]').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Файл не сохранён')
    expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Копия основания')
    await wrapper.get('[data-create-receipt]').trigger('submit'); await flushPromises()
    expect([documentWrites, uploads, receiptWrites]).toEqual([1, 2, 0])
    expect(router.currentRoute.value.path).toBe('/intake')
    wrapper.unmount()
  })
})
