import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { department, expertise, receipt, specialty, testRouter } from '../../test/intakeFixtures'
import ReceiptPage from './ReceiptPage.vue'

async function setup(loseFirstPost = false, rejectFirstPost = false) {
  let next = 483
  const posts: { body: Record<string, unknown>; key: string | null }[] = [], hints: string[] = []
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
    if (init?.method === 'POST') {
      posts.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') })
      if (loseFirstPost && posts.length === 1) throw new TypeError('Ответ потерян')
      if (rejectFirstPost && posts.length === 1) return json({ code: 'validation_error', message: 'Регистрация отклонена' }, 400)
      return json(path.includes('complex-expertises') ? { expertises: [expertise, { ...expertise, id: 'work-2' }] } : expertise, 201)
    }
    if (path.includes('/references/')) return json(page(path.includes('departments') ? [department] : [specialty, { ...specialty, id: 's-16', code: '16.1' }]))
    if (path.includes('number-hint')) { hints.push(path); return json({ last_number: next === 1 ? null : `${next - 1}/4-1-26`, next_sequence: next }) }
    return json(receipt)
  })
  const router = await testRouter('/receipts/receipt-1')
  const wrapper = mount(ReceiptPage, { global: { plugins: [sessionWith('receipts.view', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
  await flushPromises()
  await wrapper.get('[name="specialty_id"]').setValue(specialty.id)
  return { wrapper, router, posts, hints, setNext(value: number) { next = value } }
}

describe('out-of-sequence number confirmation', () => {
  it('saves the next number without requesting additional confirmation', async () => {
    const { wrapper, posts } = await setup()
    await wrapper.get('[name="registration_number"]').setValue('483/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(1)
    expect(wrapper.find('[data-sequence-warning]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('allows correction or explicit confirmation and keeps retries of a lost response unchanged', async () => {
    const { wrapper, router, posts, hints, setNext } = await setup(true)
    await wrapper.get('[name="registration_number"]').setValue('999/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(0)
    expect(wrapper.get('[data-sequence-warning]').text()).toContain('483/4-1-26')
    expect(wrapper.get('[data-sequence-warning]').text()).toContain('999/4-1-26')
    await wrapper.get('[data-edit-sequence]').trigger('click'); await flushPromises()
    expect((wrapper.get('[name="registration_number"]').element as HTMLInputElement).value).toBe('999/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-confirm-sequence]').trigger('click'); await flushPromises()
    expect(posts).toHaveLength(1)
    expect(posts[0]?.body.registration_number).toBe('999/4-1-26')
    const checked = hints.length
    setNext(1000)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(2)
    expect(posts[1]).toEqual(posts[0])
    expect(hints).toHaveLength(checked)
    expect(router.currentRoute.value.path).toBe('/expertises/work-1')
    wrapper.unmount()
  })

  it('warns about a gap in a complex packet before saving any row', async () => {
    const { wrapper, posts } = await setup()
    await wrapper.get('[name="registration_number"]').setValue('483/4-1-26')
    await wrapper.get('[name="is_complex"]').setValue(true)
    await wrapper.get('[name="additional_specialty_id"]').setValue('s-16')
    await wrapper.get('[name="additional_registration_number"]').setValue('500/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(0)
    expect(wrapper.get('[data-sequence-warning]').text()).toContain('484/4-1-26')
    await wrapper.get('[data-confirm-sequence]').trigger('click'); await flushPromises()
    expect(posts).toHaveLength(1)
    expect((posts[0]?.body.works as { registration_number: string }[])[1]?.registration_number).toBe('500/4-1-26')
    wrapper.unmount()
  })

  it('checks a fresh maximum instead of trusting the earlier hint', async () => {
    const { wrapper, posts, setNext } = await setup()
    await wrapper.get('[name="registration_number"]').setValue('483/4-1-26')
    setNext(484)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(0)
    expect(wrapper.get('[data-sequence-warning]').text()).toContain('484/4-1-26')
    wrapper.unmount()
  })

  it('rechecks the sequence after a definite server rejection while preserving the retry key', async () => {
    const { wrapper, posts, setNext } = await setup(false, true)
    await wrapper.get('[name="registration_number"]').setValue('483/4-1-26')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(1)
    setNext(484)
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(posts).toHaveLength(1)
    expect(wrapper.get('[data-sequence-warning]').text()).toContain('484/4-1-26')
    await wrapper.get('[data-confirm-sequence]').trigger('click'); await flushPromises()
    expect(posts).toHaveLength(2)
    expect(posts[1]?.key).toBe(posts[0]?.key)
    wrapper.unmount()
  })

  it('uses the year in the entered number even when the helper shows another year', async () => {
    const { wrapper, posts, hints, setNext } = await setup()
    setNext(1)
    await wrapper.get('[name="registration_number"]').setValue('1/4-5-27')
    await wrapper.get('[data-register-expertise]').trigger('submit'); await flushPromises()
    expect(hints.at(-1)).toContain('year=2027')
    expect(posts).toHaveLength(1)
    wrapper.unmount()
  })
})
