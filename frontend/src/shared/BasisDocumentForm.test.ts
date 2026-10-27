import { flushPromises, mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import { ApiClient, apiKey } from '../api/client'
import { json } from '../test/fixtures'
import { basis } from '../test/intakeFixtures'
import BasisDocumentForm from './BasisDocumentForm.vue'

it('recovers a committed metadata response with one stable key and uploads to the same document', async () => {
  const creates: { key: string | null; body: string }[] = [], ids = new Map<string, string>(), uploads: string[] = []
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (path.endsWith('/documents/')) {
      const key = new Headers(init?.headers).get('Idempotency-Key'); creates.push({ key, body: String(init?.body) })
      const id = key && ids.get(key) || `document-${creates.length}`
      if (key) ids.set(key, id)
      if (creates.length === 1) throw new TypeError('Ответ метаданных потерян после commit')
      return json({ ...basis, id, source_kind: 'uploaded_copy' }, 201)
    }
    uploads.push(path)
    return json({ id: 'file-1', number: 1, original_name: 'basis.pdf', content_type: 'application/pdf', size: 4, sha256: 'abc', created_at: '2026-10-28T00:00:00Z', download_url: '/download/', preview_url: '/preview/' }, 201)
  })
  const wrapper = mount(BasisDocumentForm, { props: { departmentId: 'd-4' }, global: { provide: { [apiKey as symbol]: client } } })
  await wrapper.get('[name="document_title"]').setValue('Копия с потерянным ответом')
  await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'basis.pdf')] })
  await wrapper.get('input[type="file"]').trigger('change')
  await expect(wrapper.vm.persist()).rejects.toThrow('Ответ метаданных потерян')
  const result = await wrapper.vm.persist()
  expect(creates[0]!.key).toBeTruthy(); expect(creates[1]).toEqual(creates[0])
  expect(result.id).toBe('document-1'); expect(uploads).toEqual(['/api/v1/documents/document-1/versions/'])
  await wrapper.get('[name="document_title"]').setValue('Явно другой документ')
  await wrapper.vm.persist()
  expect(creates[2]!.key).not.toBe(creates[0]!.key)
  wrapper.unmount()
})

it('recovers a committed upload with its original command key without recreating the document', async () => {
  let documentWrites = 0, committedKey: string | null = null, attempted = false
  const version = { id: 'file-1', number: 1, original_name: 'basis.pdf', content_type: 'application/pdf', size: 4, sha256: 'abc', created_at: '2026-10-28T00:00:00Z', download_url: '/download/', preview_url: '/preview/' }
  const client = new ApiClient(async (input, init) => {
    if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (String(input).endsWith('/documents/')) { documentWrites++; return json({ ...basis, source_kind: 'uploaded_copy' }, 201) }
    const key = new Headers(init?.headers).get('Idempotency-Key')
    if (!attempted) { attempted = true; committedKey = key; throw new TypeError('Ответ потерян после записи файла') }
    return key && key === committedKey ? json(version, 201) : json({ code: 'version_conflict', message: 'Старая версия документа', field_errors: {} }, 409)
  })
  const wrapper = mount(BasisDocumentForm, { props: { departmentId: 'd-4' }, global: { provide: { [apiKey as symbol]: client } } })
  await wrapper.get('[name="document_title"]').setValue('Копия основания')
  await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
  Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'basis.pdf')] })
  await wrapper.get('input[type="file"]').trigger('change')
  await expect(wrapper.vm.persist()).rejects.toThrow('Ответ потерян после записи файла')
  const result = await wrapper.vm.persist(); await flushPromises()
  expect(result.versions).toEqual([version])
  expect(documentWrites).toBe(1)
  wrapper.unmount()
})
