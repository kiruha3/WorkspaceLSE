import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

async function setup(onWrite?: (path: string, init: RequestInit) => Promise<Response>) {
  const writes: { path: string; body: Record<string, unknown> }[] = []
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (init?.method === 'POST') {
      writes.push({ path, body: JSON.parse(String(init.body)) })
      return onWrite ? onWrite(path, init) : json(path.includes('complex-expertises') ? { expertises: [expertise, { ...expertise, id: 'work-2' }] } : expertise, 201)
    }
    if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty, { ...specialty, id: 's-16', code: '16.1' }]))
    if (path.includes('number-hint')) return json({ last_number: null, next_sequence: 1 })
    return json(receipt)
  })
  const router = await testRouter('/receipts/receipt-1')
  const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  return { wrapper, router, writes }
}

describe('complex registration with multiple numbers', () => {
  it('adds a second number without creating or naming a group, and supports more specialties', async () => {
    const { wrapper, writes } = await setup()
    expect(wrapper.findAll('[data-complex-row]')).toHaveLength(0)
    await wrapper.get('[name="is_complex"]').setValue(true)
    expect(wrapper.findAll('[data-complex-row]')).toHaveLength(1)
    expect(wrapper.find('[name="complex_group_id"]').exists()).toBe(false)
    expect(wrapper.find('[name="complex_group_title"]').exists()).toBe(false)
    await wrapper.get('[data-add-complex-row]').trigger('click')
    expect(wrapper.findAll('[data-complex-row]')).toHaveLength(2)
    await wrapper.findAll('[data-remove-complex-row]')[1]!.trigger('click')
    expect(wrapper.findAll('[data-complex-row]')).toHaveLength(1)
    expect(writes).toHaveLength(0)
    wrapper.unmount()
  })

  it('saves both rows with one POST and preserves the same payload and key after a lost response', async () => {
    const keys: string[] = []
    const { wrapper, router, writes } = await setup(async (_path, init) => {
      keys.push(new Headers(init.headers).get('Idempotency-Key') || '')
      if (keys.length === 1) throw new TypeError('Lost response')
      return json({ expertises: [expertise, { ...expertise, id: 'work-2' }] }, 201)
    })
    await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
    await wrapper.get('[name="specialty_id"]').setValue(specialty.id)
    await wrapper.get('[name="is_complex"]').setValue(true)
    const row = wrapper.get('[data-complex-row]')
    await row.get('[name="additional_department_id"]').setValue(department.id)
    await row.get('[name="additional_specialty_id"]').setValue('s-16')
    await row.get('[name="additional_registration_number"]').setValue('152/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect((row.get('[name="additional_registration_number"]').element as HTMLInputElement).value).toBe('152/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toContain('/receipts/receipt-1/complex-expertises/')
    expect(writes[0]?.body).toEqual(writes[1]?.body)
    const works = writes[0]?.body.works as { registration_number: string; specialty_id: string }[]
    expect(works.map(work => work.registration_number)).toEqual(['151/4-1-26', '152/4-1-26'])
    expect(works.map(work => work.specialty_id)).toEqual([specialty.id, 's-16'])
    expect(keys[0]).not.toBe(''); expect(keys[1]).toBe(keys[0])
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    wrapper.unmount()
  })

  it('does not submit an incomplete second row and retains ordinary registration when unchecked', async () => {
    const { wrapper, writes } = await setup()
    await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
    await wrapper.get('[name="specialty_id"]').setValue(specialty.id)
    await wrapper.get('[name="is_complex"]').setValue(true)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(0)
    await wrapper.get('[name="is_complex"]').setValue(false)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(writes[0]?.path).toContain('/receipts/receipt-1/expertises/')
    expect(writes[0]?.body.complex_group_id).toBeNull()
    wrapper.unmount()
  })
})
