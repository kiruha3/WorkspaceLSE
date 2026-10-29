import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { useSessionStore } from '../../stores/session'
import { json, page, sessionWith } from '../../test/fixtures'
import { basis, department } from '../../test/intakeFixtures'
import LetterPage from './LetterPage.vue'
import LettersPage from './LettersPage.vue'
import ExpertiseLetters from './ExpertiseLetters.vue'
import App from '../../App.vue'
import { router as applicationRouter } from '../../router'
import HomePage from '../HomePage.vue'
import type { Letter, LetterOptions } from '../../api/letters'

const actor = { id: 'employee-1', full_name: 'Делопроизводитель' }
const reference = { id: 'kind-1', code: 'request', name: 'Запрос', is_active: true, version: 1 }
const content = { id: 'revision-1', number: 1, kind: null, subject: 'Запрос материалов', body: 'Текст письма', sender_name: 'Районный суд', external_number: '', external_on: null, document_on: null, received_on: null, note: '', material: null, expertises: [], parent: null, reply_completeness: null, recipients: [{ id: 'recipient-1', name: 'Суд первый', address: '', email: '' }, { id: 'recipient-2', name: 'Суд второй', address: '', email: '' }], actor, created_at: '2026-10-28T00:00:00Z', reason: 'Создание' }
const letter: Letter = { id: 'letter-1', direction: 'outgoing', department, responsible: actor, version: 1, created_at: content.created_at, state: 'draft', received_on: null, content, content_history: [content], attachments: [], registration: null, dispatches: [], deliveries: [], receipts: [], assignment_history: [], replies: [], control: null, allowed_actions: [] }
const options: LetterOptions = { kinds: [reference], journals: [{ ...reference, id: 'journal-1', name: 'Исходящий журнал', direction: 'outgoing', department_id: null }], channels: [{ ...reference, id: 'channel-1', code: 'russian_post', name: 'Почта России' }], closure_reasons: [{ ...reference, id: 'closure-1', code: 'reply_sent', name: 'Ответ отправлен', rule: 'reply_sent' }, { ...reference, id: 'closure-2', code: 'other', name: 'Иное', rule: 'other' }], departments: [department], employees: [actor] }
const registered: Letter = { ...letter, state: 'registered', registration: { id: 'registration-1', journal: options.journals[0]!, registration_number: 'Исх-7/26', registered_on: '2026-10-28', year: 2026, revision_id: content.id, files: [], actor, created_at: content.created_at, reason: 'Учёт' } }
type Transport = ConstructorParameters<typeof ApiClient>[0]
async function open(value: Letter = letter, transport?: Transport, url = '/letters/letter-1', codes = ['letters.view', 'letters.draft', 'letters.reply']) {
  const pinia = sessionWith(...codes); useSessionStore().user!.supported_modules = ['correspondence']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/letters', component: LettersPage }, { path: '/letters/:id', component: LetterPage }, { path: '/workspace', component: { template: '<p>Рабочее место</p>' } }] })
  await router.push(url)
  const client = new ApiClient(transport ?? (async input => String(input).includes('/options/') ? json(options) : String(input).includes('-options/') ? json(page([])) : json(value)))
  const wrapper = mount(RouterView, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises()
  return { wrapper, router }
}
afterEach(() => vi.restoreAllMocks())
enableAutoUnmount(afterEach)
describe('correspondence workplace', () => {
  it.each([
    { allowed: false, detail: 'Сведения о контроле недоступны', registry: 'Недоступно' },
    { allowed: true, detail: 'На контроль не поставлено', registry: 'Не поставлено' },
  ])('distinguishes restricted control from confirmed absence (read access: $allowed)', async ({ allowed, detail, registry }) => {
    const value = { ...registered, allowed_actions: allowed ? ['control.view'] : [] }
    const card = await open(value)
    expect(card.wrapper.get('[data-control-status]').text()).toBe(detail)
    card.wrapper.unmount()
    const list = await open(value, async input => json(String(input).includes('/options/') ? options : page([value])), '/letters')
    expect(list.wrapper.get('tbody tr td:last-child').text()).toBe(registry)
  })
  it('keeps unknown facts unknown and exposes only server allowed commands', async () => {
    const { wrapper } = await open({ ...letter, allowed_actions: ['letters.register'] })
    expect(wrapper.get('[data-received-on]').text()).toBe('Неизвестно')
    expect(wrapper.get('[data-letter-kind]').text()).toBe('Не указан')
    expect(wrapper.find('[data-action="register"]').exists()).toBe(true)
    expect(wrapper.find('[data-action="send"]').exists()).toBe(false)
    expect(wrapper.find('[data-edit-draft]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('submits manual registration without replacing unknown receipt facts', async () => {
    const writes: { path: string; body: unknown; key: string | null }[] = []
    const { wrapper } = await open({ ...letter, allowed_actions: ['letters.register'] }, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ path: String(input), body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ event: { id: 'event-1' }, letter: registered }) }
      return json(String(input).includes('/options/') ? options : { ...letter, allowed_actions: ['letters.register'] })
    })
    await wrapper.get('[data-action="register"]').trigger('click')
    await wrapper.get('[name="journal_id"]').setValue('journal-1'); await wrapper.get('[name="registration_number"]').setValue('  Исх-7/26  '); await wrapper.get('[name="registered_on"]').setValue('2026-10-28'); await wrapper.get('[name="command_reason"]').setValue('  Учёт  ')
    await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    expect(writes[0]).toEqual({ path: '/api/v1/letters/letter-1/register/', body: { expected_version: 1, reason: 'Учёт', journal_id: 'journal-1', registration_number: 'Исх-7/26', registered_on: '2026-10-28' }, key: expect.any(String) })
    expect(wrapper.get('[data-received-on]').text()).toBe('Неизвестно'); wrapper.unmount()
  })
  it('records selected recipients and leaves delivery and control independent after partial send', async () => {
    const writes: unknown[] = []
    const sent: Letter = { ...registered, version: 2, state: 'partially_sent', control: { id: 'control-1', opened_on: '2026-10-28', due_on: null, due_basis: '', status: 'open', response_progress: 'partial', overdue: false, events: [] } }
    const { wrapper } = await open({ ...registered, allowed_actions: ['letters.mark_sent'] }, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); expect(String(input)).toBe('/api/v1/letters/letter-1/mark-sent/'); return json({ event: { id: 'dispatch-1' }, letter: sent }) }
      return json(String(input).includes('/options/') ? options : { ...registered, allowed_actions: ['letters.mark_sent'] })
    })
    await wrapper.get('[data-action="send"]').trigger('click'); await wrapper.get('[name="sent_on"]').setValue('2026-10-28'); await wrapper.get('[name="channel_id"]').setValue('channel-1'); await wrapper.get('[name="recipient_ids"][value="recipient-1"]').setValue(true); await wrapper.get('[name="command_reason"]').setValue('Отправлено в канцелярию')
    await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, reason: 'Отправлено в канцелярию', sent_on: '2026-10-28', channel_id: 'channel-1', recipient_ids: ['recipient-1'], tracking: '', comment: '', evidence_document_id: null }])
    expect(wrapper.get('[data-letter-state]').text()).toBe('Отправлено части адресатов'); expect(wrapper.get('[data-delivery-state]').text()).toContain('0'); expect(wrapper.get('[data-control-status]').text()).toBe('Открыт'); wrapper.unmount()
  })
  it('replays the original normalized body/key/version after response loss and refresh, bypassing native date validation', async () => {
    let version = 1; const writes: { body: string; key: string | null }[] = []
    const { wrapper } = await open({ ...letter, allowed_actions: ['letters.register'] }, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') } return json({ event: { id: 'same' }, letter: registered }) }
      return json(String(input).includes('/options/') ? options : { ...letter, version, allowed_actions: ['letters.register'] })
    })
    await wrapper.get('[data-action="register"]').trigger('click'); await wrapper.get('[name="journal_id"]').setValue('journal-1'); await wrapper.get('[name="registration_number"]').setValue('7'); await wrapper.get('[name="registered_on"]').setValue('2026-10-28'); await wrapper.get('[name="command_reason"]').setValue('Причина')
    await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises(); await wrapper.get('[data-refresh-letter]').trigger('click'); await flushPromises()
    await wrapper.get('[name="command_reason"]').setValue('  Причина  ')
    expect(wrapper.get('[data-letter-command] button[type="submit"]').attributes('formnovalidate')).toBeDefined()
    await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]); wrapper.unmount()
  })
  it('preserves a conflict draft through refresh and requires explicit acceptance of the new version', async () => {
    let version = 1; const writes: { body: Record<string, unknown>; key: string | null }[] = []
    const { wrapper } = await open({ ...registered, allowed_actions: ['letters.mark_received'] }, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ code: 'version_conflict', message: 'Обновите сведения' }, 409) }
      return json(String(input).includes('/options/') ? options : { ...registered, version, allowed_actions: ['letters.mark_received'] })
    })
    await wrapper.get('[data-action="receive"]').trigger('click'); await wrapper.get('[name="received_on"]').setValue('2026-10-28'); await wrapper.get('[name="command_reason"]').setValue('Фактическое получение'); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    version = 2; await wrapper.get('[data-refresh-letter]').trigger('click'); await flushPromises()
    expect(wrapper.get('[name="command_reason"]').element).toHaveProperty('value', 'Фактическое получение')
    await wrapper.get('[data-accept-command-version]').trigger('click'); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    expect(writes[1]!.body).toEqual({ expected_version: 2, reason: 'Фактическое получение', received_on: '2026-10-28', evidence_document_id: null }); expect(writes[1]!.key).not.toBe(writes[0]!.key); wrapper.unmount()
  })
  it('creates an incomplete reply draft with exact null fields and prefilled work and parent', async () => {
    const writes: unknown[] = []
    const { wrapper } = await open(letter, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'new' }, letter }, 201) }
      if (path.includes('/options/')) return json(options)
      if (path.includes('-options/')) return json(page([{ id: 'work-1', registration_number: '151/4', material: { id: 'material-1', title: 'Дело' } }]))
      if (path.includes('/letters/parent-1/')) return json({ ...registered, id: 'parent-1', direction: 'incoming' })
      if (path.includes('/letters/letter-1/')) return json(letter)
      return json(page([]))
    }, '/letters?create=1&expertise_id=work-1&parent_id=parent-1&direction=outgoing')
    await wrapper.get('[name="draft_reason"]').setValue('Первоначальный черновик'); await wrapper.get('[data-letter-draft]').trigger('submit'); await flushPromises()
    expect(writes[0]).toEqual({ direction: 'outgoing', department_id: null, parent_id: 'parent-1', kind_id: null, subject: '', body: '', sender_name: '', external_number: '', external_on: null, document_on: null, received_on: null, note: '', material_id: null, expertise_ids: ['work-1'], reply_completeness: null, recipients: [], reason: 'Первоначальный черновик' }); wrapper.unmount()
  })
  it('guards changes before saving and preserves URL filters in return links', async () => {
    const paths: string[] = []
    const { wrapper, router } = await open(letter, async input => { paths.push(String(input)); return json(String(input).includes('/options/') ? options : String(input).includes('-options/') ? page([]) : page([registered])) }, '/letters?search=суд&control_status=overdue&received_from=2026-10-01&page=2')
    expect(paths.some(path => path.includes('control_status=overdue') && path.includes('received_from=2026-10-01') && path.includes('page=2'))).toBe(true)
    const link = new URL(wrapper.get('[data-open-letter]').attributes('href')!, 'http://localhost'); expect(link.searchParams.get('return')).toBe('/letters?search=суд&control_status=overdue&received_from=2026-10-01&page=2')
    await router.push('/letters?create=1'); await flushPromises(); await wrapper.get('[name="subject"]').setValue('Несохранённая тема'); vi.spyOn(window, 'confirm').mockReturnValue(false)
    await router.push('/workspace'); expect(router.currentRoute.value.path).toBe('/letters'); wrapper.unmount()
  })
  it('keeps final reply creation independent from explicit control closure and reopen', async () => {
    const controlled: Letter = { ...registered, direction: 'incoming', allowed_actions: ['letters.reply', 'control.close'], control: { id: 'c-1', opened_on: '2026-10-28', due_on: null, due_basis: '', status: 'open', response_progress: 'final', overdue: false, events: [] }, replies: [{ id: 'reply-1', direction: 'outgoing', subject: 'Полный ответ', registration_number: '8', reply_completeness: 'final', state: 'sent' }] }
    const writes: unknown[] = []
    const { wrapper } = await open(controlled, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 't' }); if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); expect(String(input)).toBe('/api/v1/letters/letter-1/control/close/'); return json({ event: { id: 'closed' }, letter: { ...controlled, version: 2, allowed_actions: ['control.reopen'], control: { ...controlled.control!, status: 'closed' } } }) } return json(String(input).includes('/options/') ? options : controlled) })
    expect(wrapper.get('[data-create-reply]').attributes('href')).toContain('parent_id=letter-1'); expect(wrapper.get('[data-control-status]').text()).toBe('Открыт')
    await wrapper.get('[data-action="close"]').trigger('click'); await wrapper.get('[name="closed_on"]').setValue('2026-10-28'); await wrapper.get('[name="closure_reason_id"]').setValue('closure-1'); await wrapper.get('[name="reply_id"]').setValue('reply-1'); await wrapper.get('[name="command_reason"]').setValue('Контроль исполнен'); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises()
    expect(writes[0]).toEqual({ expected_version: 1, reason: 'Контроль исполнен', closed_on: '2026-10-28', closure_reason_id: 'closure-1', reply_id: 'reply-1', comment: '' }); expect(wrapper.find('[data-action="reopen"]').exists()).toBe(true); wrapper.unmount()
  })
  it('keeps accepted registration files distinct from later attachments and restricts private evidence', async () => {
    const file = { id: 'v1', number: 1, original_name: 'first.pdf', content_type: 'application/pdf', size: 12, sha256: '', created_at: content.created_at, download_url: '/v1/download/', preview_url: '/v1/preview/' }
    const { wrapper } = await open({ ...registered, registration: { ...registered.registration!, files: [{ ...basis, accepted_version_id: 'v1', versions: [file, { ...file, id: 'v2', number: 2, original_name: 'later.pdf', preview_url: '/v2/preview/' }] }] }, attachments: [{ id: 'a1', document: { id: 'private', restricted: true }, actor, created_at: content.created_at, reason: 'Поздний файл' }] })
    expect(wrapper.get('[data-registration-files] iframe').attributes('src')).toBe('/v1/preview/'); expect(wrapper.get('[data-attachments]').text()).toContain('Доступ к документу ограничен'); wrapper.unmount()
  })
  it('does not fetch or mount correspondence while server capability is absent, even with a read grant', async () => {
    const pinia = sessionWith('letters.view', 'letters.draft'); const paths: string[] = []
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/workspace', component: { template: '<p>Рабочее место</p>' } }, { path: '/letters', component: LettersPage }] }); await router.push('/workspace')
    const client = new ApiClient(async input => { paths.push(String(input)); return json(page([])) })
    const wrapper = mount(App, { global: { plugins: [pinia, router] } }); const linked = mount(ExpertiseLetters, { props: { expertiseId: 'work-1' }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises()
    expect(wrapper.find('nav a[href="/letters"]').exists()).toBe(false); expect(paths).toEqual([]); expect(linked.text()).toBe(''); wrapper.unmount(); linked.unmount()
  })
  it('offers the enabled journal by its read grant and fetches only the scoped work letters endpoint', async () => {
    const pinia = sessionWith('letters.view', 'letters.draft'); useSessionStore().user!.supported_modules = ['correspondence']; const paths: string[] = []
    const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/letters', '/letters/:id'].map(path => ({ path, component: { template: '<p>Рабочее место</p>' } })) }); await router.push('/workspace')
    const client = new ApiClient(async input => { paths.push(String(input)); return json(page([{ id: 'letter-1', direction: 'incoming', subject: 'Запрос', registration_number: 'Вх-1', reply_completeness: null, state: 'registered' }])) })
    const wrapper = mount(App, { global: { plugins: [pinia, router] } }); const linked = mount(ExpertiseLetters, { props: { expertiseId: 'work-1' }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises()
    expect(wrapper.find('nav a[href="/letters"]').exists()).toBe(true); expect(paths).toEqual(['/api/v1/expertises/work-1/letters/?page=1']); expect(linked.text()).toContain('Вх-1'); expect(linked.get('[data-new-work-letter]').attributes('href')).toContain('expertise_id=work-1'); wrapper.unmount(); linked.unmount()
  })
  it('reuses a prepared file and its upload key through lost upload response and attachment conflict', async () => {
    let documents = 0, uploads = 0
    const uploadKeys: (string | null)[] = [], writes: unknown[] = []
    const value = { ...registered, allowed_actions: ['letters.attach'] }
    const { wrapper } = await open(value, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (path.endsWith('/documents/')) { documents++; return json({ ...basis, id: 'new-doc', kind: 'letter', source_kind: 'uploaded_copy' }, 201) }
      if (path.endsWith('/versions/')) { uploads++; uploadKeys.push(new Headers(init?.headers).get('Idempotency-Key')); if (uploads === 1) throw new TypeError('Ответ потерян'); return json({ id: 'v1', number: 1, original_name: 'letter.pdf', content_type: 'application/pdf', size: 1, sha256: '', created_at: content.created_at, download_url: '/download/', preview_url: null }, 201) }
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ code: 'version_conflict', message: 'Обновите письмо' }, 409) }
      return json(path.includes('/options/') ? options : value)
    }, '/letters/letter-1', ['letters.view', 'documents.upload'])
    await wrapper.get('[data-start-attachment]').trigger('click'); await wrapper.get('[data-document-new]').trigger('click'); await wrapper.get('[name="attachment_reason"]').setValue('Позднее приложение'); await wrapper.get('[name="document_title"]').setValue('Скан письма'); await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
    Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'letter.pdf')] }); await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-attach-letter]').trigger('submit'); await flushPromises(); expect(writes).toEqual([])
    await wrapper.get('[data-attach-letter]').trigger('submit'); await flushPromises()
    expect(documents).toBe(1); expect(uploadKeys[1]).toBe(uploadKeys[0]); expect(writes).toEqual([{ expected_version: 1, reason: 'Позднее приложение', document_id: 'new-doc' }]); expect(wrapper.get('[name="document_title"]').element).toHaveProperty('value', 'Скан письма'); wrapper.unmount()
  })
  it.each([
    { action: 'deliver', permission: 'letters.mark_delivered', endpoint: 'mark-delivered', fields: { delivered_on: '2026-10-28', dispatch_id: 'dispatch-1', recipient_id: 'recipient-1' }, want: { expected_version: 1, reason: 'Подтверждённый факт', delivered_on: '2026-10-28', dispatch_id: 'dispatch-1', recipient_id: 'recipient-1', evidence_document_id: null } },
    { action: 'assign', permission: 'control.assign', endpoint: 'assign', fields: { responsible_id: 'employee-1' }, want: { expected_version: 1, reason: 'Подтверждённый факт', responsible_id: 'employee-1' } },
    { action: 'control', permission: 'control.assign', endpoint: 'control', fields: { opened_on: '2026-10-28' }, want: { expected_version: 1, reason: 'Подтверждённый факт', opened_on: '2026-10-28', due_on: null, due_basis: '' } },
    { action: 'deadline', permission: 'control.assign', endpoint: 'control/deadline', fields: { due_on: '2026-11-30', due_basis: '  Письмо суда  ' }, want: { expected_version: 1, reason: 'Подтверждённый факт', due_on: '2026-11-30', due_basis: 'Письмо суда' } },
    { action: 'reopen', permission: 'control.reopen', endpoint: 'control/reopen', fields: { reopened_on: '2026-10-28', comment: '  Появились дополнительные вопросы  ' }, want: { expected_version: 1, reason: 'Подтверждённый факт', reopened_on: '2026-10-28', comment: 'Появились дополнительные вопросы' } },
  ])('sends the exact $endpoint command without an unrelated state mutation', async ({ action, permission, endpoint, fields, want }) => {
    const value: Letter = { ...registered, allowed_actions: [permission], dispatches: [{ id: 'dispatch-1', sent_on: '2026-10-28', channel: options.channels[0]!, recipient_ids: ['recipient-1'], tracking: '', comment: '', evidence: null, files: [], actor, created_at: content.created_at, reason: 'Отправка' }], control: ['deadline', 'reopen'].includes(action) ? { id: 'c1', opened_on: '2026-10-28', due_on: null, due_basis: '', status: action === 'reopen' ? 'closed' : 'open', response_progress: 'none', overdue: false, events: [] } : null }
    const writes: unknown[] = []
    const { wrapper } = await open(value, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { expect(String(input)).toBe(`/api/v1/letters/letter-1/${endpoint}/`); expect(new Headers(init.headers).get('Idempotency-Key')).toBeTruthy(); writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'fact-1' }, letter: { ...value, version: 2 } }) } return json(String(input).includes('/options/') ? options : value) })
    await wrapper.get(`[data-action="${action}"]`).trigger('click')
    for (const [name, value] of Object.entries(fields)) await wrapper.get(`[name="${name}"]`).setValue(value)
    await wrapper.get('[name="command_reason"]').setValue('  Подтверждённый факт  '); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises(); expect(writes).toEqual([want]); wrapper.unmount()
  })
  it('saves an additional reply draft without sending parent or registration fields', async () => {
    const value: Letter = { ...letter, allowed_actions: ['letters.draft'], content: { ...content, parent: { id: 'parent-1', subject: 'Запрос', direction: 'incoming', registration_number: 'Вх-1' }, reply_completeness: 'partial' } }
    const writes: unknown[] = []
    const { wrapper } = await open(value, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { expect(String(input)).toBe('/api/v1/letters/letter-1/draft/'); writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'revision-2' }, letter: { ...value, version: 2 } }) } if (String(input).includes('-options/')) return json(page([])); return json(String(input).includes('/options/') ? options : value) })
    await wrapper.get('[data-edit-draft]').trigger('click'); await flushPromises(); await wrapper.get('[name="reply_completeness"]').setValue('additional'); await wrapper.get('[name="draft_reason"]').setValue('Уточнение'); await wrapper.get('[data-letter-draft]').trigger('submit'); await flushPromises()
    expect(writes[0]).toEqual({ expected_version: 1, reason: 'Уточнение', kind_id: null, subject: 'Запрос материалов', body: 'Текст письма', sender_name: 'Районный суд', external_number: '', external_on: null, document_on: null, received_on: null, note: '', material_id: null, expertise_ids: [], reply_completeness: 'additional', recipients: [{ name: 'Суд первый', address: '', email: '' }, { name: 'Суд второй', address: '', email: '' }] }); wrapper.unmount()
  })
  it('keeps the content base version when server details refresh before the first draft save', async () => {
    let version = 1
    const writes: { body: Record<string, unknown>; key: string | null }[] = []
    const value = { ...letter, allowed_actions: ['letters.draft'] }
    const { wrapper } = await open(value, async (input, init) => {
      const path = String(input)
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') {
        const body = JSON.parse(String(init.body))
        writes.push({ body, key: new Headers(init.headers).get('Idempotency-Key') })
        if (body.expected_version !== version) return json({ code: 'version_conflict', message: 'Обновите сведения' }, 409)
        return json({ event: { id: 'revision-3' }, letter: { ...value, version: 3 } })
      }
      if (path.includes('-options/')) return json(page([]))
      return json(path.includes('/options/') ? options : { ...value, version, content: { ...content, body: version === 1 ? 'Текст письма' : 'Правка второго редактора' } })
    })
    await wrapper.get('[data-edit-draft]').trigger('click'); await flushPromises()
    await wrapper.get('[name="subject"]').setValue('Моя правка темы')
    await wrapper.get('[name="draft_reason"]').setValue('Уточнение темы')
    version = 2
    await wrapper.get('[data-refresh-letter]').trigger('click'); await flushPromises()
    await wrapper.get('[data-letter-draft]').trigger('submit'); await flushPromises()
    expect(writes[0]!.body.expected_version).toBe(1)
    expect(wrapper.get('[name="body"]').element).toHaveProperty('value', 'Текст письма')
    expect(wrapper.get('[name="subject"]').element).toHaveProperty('value', 'Моя правка темы')
    expect(wrapper.text()).toContain('Правка второго редактора')
    await wrapper.get('[data-accept-draft-version]').trigger('click')
    await wrapper.get('[data-letter-draft]').trigger('submit'); await flushPromises()
    expect(writes[1]!.body.expected_version).toBe(2)
    expect(writes[1]!.body.subject).toBe('Моя правка темы')
    expect(writes[1]!.key).not.toBe(writes[0]!.key)
  })
  it('preserves a denied command draft when current server permissions are revoked', async () => {
    let revoked = false; let posts = 0
    const { wrapper } = await open({ ...registered, allowed_actions: ['letters.mark_received'] }, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { posts++; revoked = true; return json({ code: 'forbidden', message: 'Доступ отозван' }, 403) } return json(String(input).includes('/options/') ? options : { ...registered, allowed_actions: revoked ? [] : ['letters.mark_received'] }) })
    await wrapper.get('[data-action="receive"]').trigger('click'); await wrapper.get('[name="received_on"]').setValue('2026-10-28'); await wrapper.get('[name="command_reason"]').setValue('Зарегистрированное получение'); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises(); await wrapper.get('[data-refresh-letter]').trigger('click'); await flushPromises()
    expect(wrapper.get('[name="command_reason"]').element).toHaveProperty('value', 'Зарегистрированное получение'); expect(wrapper.get('[data-letter-command] button[type="submit"]').attributes('disabled')).toBeDefined(); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises(); expect(posts).toBe(1); wrapper.unmount()
  })
  it('cancels a late detail GET when a command returns the current server projection', async () => {
    let resolveLate: ((response: Response) => void) | undefined; let detailCalls = 0
    const { wrapper } = await open({ ...letter, allowed_actions: ['letters.register'] }, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') return json({ event: { id: 'r-1' }, letter: registered }); if (String(input).includes('/options/')) return json(options); detailCalls++; if (detailCalls > 1) return new Promise<Response>(resolve => { resolveLate = resolve }); return json({ ...letter, allowed_actions: ['letters.register'] }) })
    await wrapper.get('[data-action="register"]').trigger('click'); await wrapper.get('[name="journal_id"]').setValue('journal-1'); await wrapper.get('[name="registration_number"]').setValue('7'); await wrapper.get('[name="registered_on"]').setValue('2026-10-28'); await wrapper.get('[name="command_reason"]').setValue('Учёт'); await wrapper.get('[data-refresh-letter]').trigger('click'); await flushPromises(); await wrapper.get('[data-letter-command]').trigger('submit'); await flushPromises(); resolveLate!(json(letter)); await flushPromises(); expect(wrapper.get('[data-letter-state]').text()).toBe('Зарегистрировано'); wrapper.unmount()
  })
  it('uses safe return links and blocks direct routes without the server module or read permission', async () => {
    const { wrapper } = await open(letter, undefined, '/letters/letter-1?return=https://example.test/'); expect(wrapper.get('[data-back-to-letters]').attributes('href')).toBe('/letters'); wrapper.unmount()
    sessionWith('letters.view'); await applicationRouter.push('/letters'); expect(applicationRouter.currentRoute.value.path).toBe('/workspace')
    useSessionStore().user!.supported_modules = ['correspondence']; await applicationRouter.push('/letters'); expect(applicationRouter.currentRoute.value.path).toBe('/letters')
    useSessionStore().user!.access = {}; await applicationRouter.push('/letters/letter-1'); expect(applicationRouter.currentRoute.value.path).toBe('/workspace')
  })
  it('offers the home module only when both capability and read access exist', async () => {
    const pinia = sessionWith('letters.view'), router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/letters'].map(path => ({ path, component: { template: '<p />' } })) }); await router.push('/workspace')
    const wrapper = mount(HomePage, { global: { plugins: [pinia, router] } }); expect(wrapper.find('a[href="/letters"]').exists()).toBe(false); useSessionStore().user!.supported_modules = ['correspondence']; await flushPromises(); expect(wrapper.find('a[href="/letters"]').exists()).toBe(true); useSessionStore().user!.access = {}; await flushPromises(); expect(wrapper.find('a[href="/letters"]').exists()).toBe(false); wrapper.unmount()
  })
  it('preserves an unsaved content draft when an independent attachment command succeeds', async () => {
    const value = { ...letter, allowed_actions: ['letters.draft', 'letters.attach'] }
    const searches: string[] = [], writes: unknown[] = []
    const { wrapper } = await open(value, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (String(input).includes('/documents/?')) { searches.push(String(input)); return json(page([{ ...basis, title: 'Скан из суда' }])) } if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'a1' }, letter: { ...value, version: 2, attachments: [{ id: 'a1', document: basis, actor, created_at: content.created_at, reason: 'Приложение' }] } }) } if (String(input).includes('-options/')) return json(page([])); return json(String(input).includes('/options/') ? options : value) }, '/letters/letter-1', ['letters.view', 'letters.draft', 'documents.view'])
    await wrapper.get('[data-edit-draft]').trigger('click'); await flushPromises(); await wrapper.get('[name="subject"]').setValue('Ещё не сохранённая тема'); await wrapper.get('[data-start-attachment]').trigger('click'); await flushPromises()
    expect(wrapper.find('input[name="attachment_document_id"]').exists()).toBe(false)
    await wrapper.get('[data-document-search]').setValue('Скан'); await wrapper.get('[data-document-find]').trigger('click'); await flushPromises()
    expect(searches.some(path => path.includes('search=%D0%A1%D0%BA%D0%B0%D0%BD'))).toBe(true)
    expect(wrapper.get('[name="attachment_document_id"]').text()).toContain('Скан из суда')
    expect(writes).toEqual([])
    await wrapper.get('[name="attachment_document_id"]').setValue(basis.id); await wrapper.get('[name="attachment_reason"]').setValue('Приложение'); await wrapper.get('[data-attach-letter]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, reason: 'Приложение', document_id: basis.id }])
    expect(wrapper.get('[name="subject"]').element).toHaveProperty('value', 'Ещё не сохранённая тема'); wrapper.unmount()
  })
})
