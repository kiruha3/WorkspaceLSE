import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

async function setup() {
  let next = 483, fail = false
  const methods: string[] = []
  const client = new ApiClient(async (input, init) => {
    const path = String(input); methods.push(init?.method || 'GET')
    if (path.includes('/references/')) return json(page(path.includes('departments') ? [department, { ...department, id: 'd-3', code: '3', name: 'Отдел 3' }, { ...department, id: 'd-aup', code: 'aup', name: 'АУП' }] : [specialty]))
    if (path.includes('number-hint')) return fail ? json({ code: 'unavailable', message: 'Не удалось подобрать номер' }, 503) : json({ last_number: '482/4-1-26', next_sequence: next })
    return json(receipt)
  })
  const router = await testRouter('/receipts/receipt-1')
  const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  return { wrapper, methods, setNext(value: number) { next = value }, fail() { fail = true } }
}

describe('fill registration numbers explicitly', () => {
  it('requires a selected category and fills a fresh next number without saving a work', async () => {
    const { wrapper, methods, setNext } = await setup()
    expect(wrapper.get('[data-fill-registration-number]').attributes('disabled')).toBeDefined()
    await wrapper.get('[name="number_category"]').setValue('2')
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('')
    setNext(484)
    await wrapper.get('[data-fill-registration-number]').trigger('click'); await flushPromises()
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('484/4-2-26')
    await wrapper.get('[name="number_category"]').setValue('6')
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('484/4-2-26')
    expect(methods.every(method => method === 'GET')).toBe(true)
    wrapper.unmount()
  })

  it('fills consecutive complex numbers using each row department and the selected year', async () => {
    const { wrapper, setNext } = await setup()
    await wrapper.get('[name="department_id"]').setValue('d-3')
    await wrapper.get('[name="is_complex"]').setValue(true)
    await wrapper.get('[name="additional_department_id"]').setValue(department.id)
    await wrapper.get('[name="number_category"]').setValue('5')
    await wrapper.get('[name="hint_year"]').setValue('2027'); await flushPromises()
    setNext(1)
    await wrapper.get('[data-fill-registration-number]').trigger('click'); await flushPromises()
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('1/3-5-27')
    expect((wrapper.get('[name="additional_registration_number"]').element as HTMLInputElement).value).toBe('2/4-5-27')
    wrapper.unmount()
  })

  it('preserves entered numbers when fetching the next number fails', async () => {
    const state = await setup(), { wrapper } = state
    await wrapper.get('[name="number_category"]').setValue('1')
    await wrapper.get('[name="registration_number"]').setValue('999/4-1-26')
    state.fail()
    await wrapper.get('[data-fill-registration-number]').trigger('click'); await flushPromises()
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('999/4-1-26')
    expect(wrapper.text()).toContain('Не удалось подобрать номер')
    expect(wrapper.get('[data-fill-registration-number]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })

  it('does not build a number with an administrative department code', async () => {
    const { wrapper } = await setup()
    await wrapper.get('[name="number_category"]').setValue('1')
    await wrapper.get('[name="department_id"]').setValue('d-aup'); await flushPromises()
    expect(wrapper.get('[data-fill-registration-number]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
