import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

enableAutoUnmount(afterEach)
async function open() {
  const writes: { body: Record<string, unknown>; key: string | null }[] = []
  const router = await testRouter('/receipts/receipt-1')
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (path.endsWith('/expertises/') && init?.method === 'POST') {
      writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') })
      throw new TypeError('Ответ потерян')
    }
    if (path.includes('/references/departments/')) return json(page([department]))
    if (path.includes('/references/specialties/')) return json(page([
      { ...specialty, id: 's-16-1', code: '16.1' }, { ...specialty, id: 's-16-2', code: '16.2' }, specialty,
    ]))
    if (path.includes('number-hint')) return json({ last_number: '150/4-1-26', next_sequence: 151 })
    if (path.includes('/complex-groups/')) return json(page([]))
    return json({ ...receipt })
  })
  const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
  return { wrapper, writes }
}

it.each(['s-16-1', 's-16-2'])('registers %s with an optional construction flag and stable unchanged retry', async id => {
  const { wrapper, writes } = await open()
  await wrapper.get('[name="specialty_id"]').setValue(id)
  await wrapper.get('[name="decree3214"]').setValue(true)
  await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
  expect(writes[0]!.body).toMatchObject({ specialty_id: id, decree3214: true })
  await wrapper.findAll('button').find(b => b.text() === 'Обновить серверные сведения')!.trigger('click'); await flushPromises()
  await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
  expect(writes[1]).toEqual(writes[0])
  await wrapper.get('[name="decree3214"]').setValue(false)
  await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
  expect(writes[2]!.body.decree3214).toBe(false)
  expect(writes[2]!.key).not.toBe(writes[0]!.key)
})

it('drops a stale construction flag when switching to another specialty', async () => {
  const { wrapper, writes } = await open()
  expect(wrapper.find('[name="decree3214"]').exists()).toBe(false)
  await wrapper.get('[name="specialty_id"]').setValue('s-16-1')
  await wrapper.get('[name="decree3214"]').setValue(true)
  await wrapper.get('[name="specialty_id"]').setValue('s-18')
  expect(wrapper.find('[name="decree3214"]').exists()).toBe(false)
  await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
  expect(writes[0]!.body).not.toHaveProperty('decree3214')
  await wrapper.get('[name="specialty_id"]').setValue('s-16-2')
  expect((wrapper.get('[name="decree3214"]').element as HTMLInputElement).checked).toBe(false)
})
