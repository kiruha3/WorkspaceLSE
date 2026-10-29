import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

async function setup(onWrite?: (input: string, init: RequestInit) => Promise<Response>) {
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (init?.method === 'POST') return onWrite ? onWrite(path, init) : json(expertise, 201)
    if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty]))
    if (path.includes('number-hint')) return json({ last_number: null, next_sequence: 1 })
    if (path.includes('/complex-groups/')) return json(page([{ id: 'internal-group-id', title: '' }]))
    return json(receipt)
  })
  const router = await testRouter('/receipts/receipt-1')
  const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  return { wrapper, router }
}

describe('complex expertise registration', () => {
  it('shows group controls only for an explicitly selected complex expertise and hides internal IDs', async () => {
    const { wrapper } = await setup()
    expect(wrapper.find('[name="complex_group_id"]').exists()).toBe(false)
    await wrapper.get('[name="is_complex"]').setValue(true)
    expect(wrapper.get('[name="complex_group_id"]').text()).toContain('Без названия')
    expect(wrapper.get('[name="complex_group_id"]').text()).not.toContain('internal-group-id')
    expect(wrapper.get('[data-create-complex-group]').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="complex_group_title"]').setValue('   ')
    expect(wrapper.get('[data-create-complex-group]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('retries a lost creation response with the same key and selects the group once', async () => {
    const keys: string[] = []
    const { wrapper } = await setup(async (_path, init) => {
      keys.push(new Headers(init.headers).get('Idempotency-Key') || '')
      if (keys.length === 1) throw new TypeError('Lost response')
      return json({ id: 'named-group', title: 'Комплексное исследование по делу № 12' }, 201)
    })
    await wrapper.get('[name="is_complex"]').setValue(true)
    await wrapper.get('[name="complex_group_title"]').setValue('Комплексное исследование по делу № 12')
    await wrapper.get('[data-create-complex-group]').trigger('click'); await flushPromises()
    await wrapper.get('[data-create-complex-group]').trigger('click'); await flushPromises()
    expect(keys[0]).not.toBe('')
    expect(keys[1]).toBe(keys[0])
    expect((wrapper.get('[name="complex_group_id"]').element as HTMLSelectElement).value).toBe('named-group')
    expect(wrapper.findAll('option[value="named-group"]')).toHaveLength(1)
    expect(wrapper.get('[data-create-complex-group]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })

  it('requires a chosen group for complex registration and clears it when the complex flag is removed', async () => {
    const bodies: Record<string, unknown>[] = []
    const { wrapper } = await setup(async (_path, init) => {
      bodies.push(JSON.parse(String(init.body)))
      return json(expertise, 201)
    })
    await wrapper.get('[name="registration_number"]').setValue('151/4-1-26')
    await wrapper.get('[name="specialty_id"]').setValue(specialty.id)
    await wrapper.get('[name="is_complex"]').setValue(true)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(bodies).toHaveLength(0)
    await wrapper.get('[name="complex_group_id"]').setValue('internal-group-id')
    await wrapper.get('[name="is_complex"]').setValue(false)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(bodies[0]?.complex_group_id).toBeNull()
    wrapper.unmount()
  })
})
