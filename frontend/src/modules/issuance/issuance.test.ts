import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { ApiClient, apiKey } from '../../api/client'
import type { IssuePackage, IssueOptions, IssueWork } from '../../api/issuance'
import { useSessionStore } from '../../stores/session'
import { json, page, sessionWith } from '../../test/fixtures'
import { basis, department } from '../../test/intakeFixtures'
import IssuePackagePage from './IssuePackagePage.vue'
import IssuePackagesPage from './IssuePackagesPage.vue'
import ExpertiseIssueStatus from './ExpertiseIssueStatus.vue'
import App from '../../App.vue'
import HomePage from '../HomePage.vue'
import { router as applicationRouter } from '../../router'

const actor = { id: 'actor-1', full_name: 'Делопроизводитель' }, material = { id: 'material-1', title: 'Учебный материал' }
const revision = { id: 'revision-1', number: 1, materials_description: 'Два тома', note: '', items: [], billing: [{ expertise_id: 'work-1', is_paid: false as boolean | null }], actor, created_at: '2026-10-28T00:00:00Z', reason: 'Подготовка' }
const work: IssueWork = { id: 'work-1', registration_number: '151/4-1-26', category_code: '1', state: 'completed', department, is_commission: false, is_paid: false, closure: { id: 'closure-1', kind: 'completed', ended_on: '2026-10-28', result_kind: 'expert_conclusion', document: { ...basis, kind: 'expert_conclusion', accepted_version_id: null } }, required_items: ['expert_subscription', 'cover_letter', 'notification'] }
const pkg: IssuePackage = { id: 'package-1', material, version: 1, state: 'draft', content: revision, content_history: [revision], works: [work], readiness: { blockers: [{ code: 'missing_item', field: 'items', message: 'Не хватает подписки', expertise_id: 'work-1' }], can_check: false, can_issue: false, check_current: false }, checks: [], issuance: null, allowed_actions: ['issue.prepare', 'issue.check', 'issue.confirm'] }
const options: IssueOptions = { methods: [{ id: 'method-1', code: 'in_person', name: 'Лично', version: 1, is_active: true }], item_kinds: [{ code: 'expert_subscription', name: 'Подписка эксперта', document_kinds: ['expert_subscription'] }, { code: 'cover_letter', name: 'Сопроводительное', document_kinds: ['cover_letter', 'letter'] }, { code: 'notification', name: 'Уведомление', document_kinds: ['notification', 'letter'] }, { code: 'invoice', name: 'Счёт', document_kinds: ['invoice'] }, { code: 'other', name: 'Прочее', document_kinds: ['letter'] }] }
const ready: IssuePackage = { ...pkg, state: 'checked', readiness: { blockers: [], can_check: true, can_issue: true, check_current: true } }
type Transport = ConstructorParameters<typeof ApiClient>[0]
async function open(value: IssuePackage = pkg, transport?: Transport, url = '/issue-packages/package-1', codes = ['issue.view', 'issue.prepare', 'issue.check', 'issue.confirm']) {
  const pinia = sessionWith(...codes); useSessionStore().user!.supported_modules = ['issuance']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/issue-packages', component: IssuePackagesPage }, { path: '/issue-packages/new', component: IssuePackagePage }, { path: '/issue-packages/:id', component: IssuePackagePage }, { path: '/expertises/:id', component: { template: '<p>Экспертиза</p>' } }, { path: '/workspace', component: { template: '<p>Рабочее место</p>' } }] }); await router.push(url)
  const client = new ApiClient(transport ?? (async input => String(input).includes('/options/') ? json(options) : String(input).includes('/document-options/') ? json(page([])) : json(value)))
  const wrapper = mount(RouterView, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises(); return { wrapper, router }
}
afterEach(() => vi.restoreAllMocks()); enableAutoUnmount(afterEach)
describe('material issuance workplace', () => {
  it('edits independent nullable payability for every work and sends explicit revision facts', async () => {
    const writes: Record<string, unknown>[] = []
    const value = { ...pkg, works: [work, { ...work, id: 'work-2', registration_number: '152/4-6-26', is_paid: null }] }
    const { wrapper } = await open(value, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'saved' }, package: value }) }
      return json(String(input).includes('/options/') ? options : value)
    })
    await wrapper.get('[data-edit-issue-package]').trigger('click')
    expect(wrapper.get('[name="billing_work-1"]').element).toHaveProperty('value', 'false')
    expect(wrapper.get('[name="billing_work-2"]').element).toHaveProperty('value', '')
    await wrapper.get('[name="billing_work-1"]').setValue('true')
    await wrapper.get('[name="billing_work-2"]').setValue('false')
    await wrapper.get('[name="package_reason"]').setValue('Платность уточнена')
    await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    expect(writes[0]!.billing).toEqual([{ expertise_id: 'work-1', is_paid: true }, { expertise_id: 'work-2', is_paid: false }])
  })
  it('keeps unknown payability distinct from free, shows research act and the server invoice requirement', async () => {
    const document = { ...basis, kind: 'research_act' as const, title: 'Акт исследования' }
    const value = { ...pkg, works: [{ ...work, category_code: '6', is_paid: null, closure: { ...work.closure!, result_kind: 'research_act', document }, required_items: ['expert_subscription', 'cover_letter', 'invoice'] }], readiness: { ...pkg.readiness, blockers: [{ code: 'billing_unknown', field: 'billing', message: 'Уточните платность работы перед выдачей.', expertise_id: work.id }] } }
    const { wrapper } = await open(value)
    expect(wrapper.get('[data-work-billing="work-1"]').text()).toContain('Не уточнено')
    expect(wrapper.get('[data-issue-work="work-1"]').text()).toContain('Акт исследования')
    expect(wrapper.get('[data-issue-work="work-1"]').text()).toContain('Счёт')
    expect(wrapper.get('[data-issue-readiness]').text()).toContain('Уточните платность')
    await wrapper.get('[data-edit-issue-package]').trigger('click')
    expect(wrapper.get('[name="billing_work-1"]').element).toHaveProperty('value', '')
  })
  it('renders saved payability in each historical revision rather than the current value', async () => {
    const old = { ...revision, billing: [{ expertise_id: work.id, is_paid: false }] }
    const current = { ...revision, id: 'revision-2', number: 2, billing: [{ expertise_id: work.id, is_paid: true }] }
    const { wrapper } = await open({ ...pkg, content: current, content_history: [old, current], works: [{ ...work, is_paid: true }] })
    expect(wrapper.get('[data-billing-revision="revision-1"]').text()).toContain('Не платная')
    expect(wrapper.get('[data-billing-revision="revision-2"]').text()).toContain('Платная')
  })
  it.each([403, 409])('retains chosen payability after HTTP %s and a newer server GET', async status => {
    let refreshed = false
    const writes: Record<string, unknown>[] = []
    const { wrapper } = await open(pkg, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); refreshed = true; return json({ code: status === 409 ? 'version_conflict' : 'forbidden', message: 'Ввод сохранён' }, status) }
      return json(String(input).includes('/options/') ? options : { ...pkg, version: refreshed ? 2 : 1, allowed_actions: status === 403 && refreshed ? [] : pkg.allowed_actions })
    })
    await wrapper.get('[data-edit-issue-package]').trigger('click')
    await wrapper.get('[name="billing_work-1"]').setValue('true')
    await wrapper.get('[name="package_reason"]').setValue('Уточнение')
    await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises()
    expect(wrapper.get('[name="billing_work-1"]').element).toHaveProperty('value', 'true')
    expect(writes[0]!.billing).toEqual([{ expertise_id: work.id, is_paid: true }])
    if (status === 403) expect(wrapper.get('[data-issue-package-draft] button[type="submit"]').attributes('disabled')).toBeDefined()
    else {
      await wrapper.get('[data-accept-package-version]').trigger('click')
      await wrapper.get('[name="billing_work-1"]').setValue('')
      await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
      expect(writes[1]!.billing).toEqual([{ expertise_id: work.id, is_paid: null }])
    }
  })
  it('replays the same paid-work facts after lost response and refresh, without a second revision key', async () => {
    const writes: { body: string; key: string | null }[] = []
    const { wrapper } = await open(pkg, async (input, init) => {
      if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' })
      if (init?.method === 'POST') { writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) throw new TypeError('Ответ потерян'); return json({ event: { id: 'same' }, package: { ...pkg, version: 2 } }) }
      return json(String(input).includes('/options/') ? options : { ...pkg, version: writes.length ? 2 : 1, works: writes.length ? [work, { ...work, id: 'new-work', registration_number: '152/4-1-26', is_paid: null }] : [work] })
    })
    await wrapper.get('[data-edit-issue-package]').trigger('click')
    await wrapper.get('[name="billing_work-1"]').setValue('true')
    await wrapper.get('[name="package_reason"]').setValue('Платная работа')
    await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises()
    await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0])
    expect(JSON.parse(writes[0]!.body).billing).toEqual([{ expertise_id: work.id, is_paid: true }])
  })
  it.each(['uploaded_copy', 'paper_original'] as const)('pins the main issued %s supplement to its issuing check, not latest or another check', async source => {
    const first = { id: 'supp-v1', number: 1, original_name: 'accepted.pdf', content_type: 'application/pdf', size: 12, sha256: '', created_at: revision.created_at, download_url: '/supp-v1/download/', preview_url: '/supp-v1/preview/' }
    const document = { ...basis, id: 'subscription', kind: 'expert_subscription' as const, source_kind: source, versions: [first, { ...first, id: 'supp-v2', number: 2, original_name: 'later.pdf', download_url: '/supp-v2/download/', preview_url: '/supp-v2/preview/' }] }
    const content = { ...revision, items: [{ id: 'item-1', kind: 'expert_subscription' as const, expertise_id: work.id, document, note: '' }] }
    const check = (id: string, accepted_version_id: string | null) => ({ id, revision_id: revision.id, actor, created_at: revision.created_at, reason: 'Проверка', works: [], files: [{ item_id: 'item-1', closure_id: null, document: { ...document, accepted_version_id } }] })
    const issuance = { id: 'issue-1', check_id: 'issuing-check', issued_on: '2026-10-28', method: options.methods[0]!, recipient_name: 'ДЕМО', recipient_basis: 'ДЕМО', tracking: '', comment: '', evidence: null, actor, created_at: revision.created_at, reason: 'ДЕМО' }
    const { wrapper } = await open({ ...ready, state: 'issued', content, content_history: [content], checks: [check('another-check', 'supp-v2'), check('issuing-check', source === 'uploaded_copy' ? 'supp-v1' : null)], issuance, allowed_actions: [] })
    const main = wrapper.get('[data-issue-work="work-1"] .inset-form')
    if (source === 'uploaded_copy') {
      expect(main.get('iframe').attributes('src')).toBe('/supp-v1/preview/')
      expect(main.get('a[download]').attributes('href')).toBe('/supp-v1/download/')
      await main.get('select').setValue('supp-v2')
    } else {
      expect(main.find('iframe').exists()).toBe(false)
      expect(main.find('a[download]').exists()).toBe(false)
      expect(main.text()).toContain('Подтверждённая версия файла не установлена')
      await main.get('select').setValue('supp-v2')
    }
    expect(main.get('[data-unconfirmed-file]').text()).toContain('не подтверждена этим событием')
    wrapper.unmount()
  })
  it('shows every work requirement and server blocker without treating completed work as issued', async () => {
    const { wrapper } = await open({ ...pkg, works: [work, { ...work, id: 'work-2', registration_number: '152/4-2-26', category_code: '2', required_items: ['expert_subscription', 'cover_letter', 'invoice'] }] })
    expect(wrapper.get('[data-issue-fact]').text()).toContain('Не выдано'); expect(wrapper.get('[data-issue-work="work-1"]').text()).toContain('Уведомление'); expect(wrapper.get('[data-issue-work="work-2"]').text()).toContain('Счёт'); expect(wrapper.get('[data-issue-readiness]').text()).toContain('Не хватает подписки'); expect(wrapper.find('[data-start-issue]').attributes('disabled')).toBeDefined(); wrapper.unmount()
  })
  it('keeps unknown policies and restricted outcome documents visible as blockers', async () => {
    const value: IssuePackage = { ...pkg, works: [{ ...work, category_code: '4', is_commission: true, closure: { ...work.closure!, document: { id: 'private', restricted: true } } }], readiness: { ...pkg.readiness, blockers: [{ code: 'policy_unconfirmed', field: 'works', message: 'Регламент категории не подтверждён' }, { code: 'commission_policy_unconfirmed', field: 'works', message: 'Число подписок комиссии не подтверждено' }] } }
    const { wrapper } = await open(value); expect(wrapper.text()).toContain('Регламент категории не подтверждён'); expect(wrapper.text()).toContain('Число подписок комиссии не подтверждено'); expect(wrapper.get('[data-issue-work="work-1"]').text()).toContain('Доступ к документу ограничен'); wrapper.unmount()
  })
  it('loads the material contract before creating and redirects an existing package without POST', async () => {
    const paths: string[] = []
    const { wrapper, router } = await open(pkg, async (input, init) => { expect(init?.method ?? 'GET').toBe('GET'); paths.push(String(input)); return json(String(input).includes('/options/') ? options : String(input).includes('/materials/') ? { material, package: pkg, can_prepare: true } : pkg) }, '/issue-packages/new?material_id=material-1')
    expect(paths[0]).toBe('/api/v1/materials/material-1/issue-packages/'); expect(router.currentRoute.value.path).toBe('/issue-packages/package-1'); expect(wrapper.find('[data-create-issue-package]').exists()).toBe(false); wrapper.unmount()
  })
  it('creates an incomplete package with an exact content body after the explicit material lookup', async () => {
    const writes: { path: string; body: unknown; key: string | null }[] = []
    const { wrapper } = await open(pkg, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { writes.push({ path: String(input), body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ event: { id: 'created' }, package: pkg }, 201) } return json(String(input).includes('/options/') ? options : String(input).includes('/materials/') ? { material, package: null, can_prepare: true } : pkg) }, '/issue-packages/new?material_id=material-1')
    await wrapper.get('[name="materials_description"]').setValue('  Два тома  '); await wrapper.get('[name="package_reason"]').setValue('  Подготовка  '); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/materials/material-1/issue-packages/', body: { materials_description: 'Два тома', note: '', items: [], billing: [], reason: 'Подготовка' }, key: expect.any(String) }]); wrapper.unmount()
  })
  it('pins a draft version to its original fields before the first save, preserving refresh and conflict', async () => {
    let version = 1; const writes: { body: Record<string, unknown>; key: string | null }[] = []
    const { wrapper } = await open(pkg, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ code: 'version_conflict', message: 'Обновите комплект' }, 409) } return json(String(input).includes('/options/') ? options : { ...pkg, version, content: { ...revision, materials_description: version === 1 ? 'Два тома' : 'Серверные три тома' } }) })
    await wrapper.get('[data-edit-issue-package]').trigger('click'); await wrapper.get('[name="materials_description"]').setValue('Мой несохранённый состав'); await wrapper.get('[name="package_reason"]').setValue('Уточнение'); version = 2; await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    expect(writes[0]!.body).toEqual({ expected_version: 1, reason: 'Уточнение', materials_description: 'Мой несохранённый состав', note: '', items: [], billing: [{ expertise_id: 'work-1', is_paid: false }] }); expect(wrapper.get('[name="materials_description"]').element).toHaveProperty('value', 'Мой несохранённый состав')
    await wrapper.get('[data-accept-package-version]').trigger('click'); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises(); expect(writes[1]!.body.expected_version).toBe(2); expect(writes[1]!.key).not.toBe(writes[0]!.key); wrapper.unmount()
  })
  it('uses the scoped server document picker and sends a complete item revision', async () => {
    const paths: string[] = [], writes: unknown[] = []
    const document = { ...basis, id: 'subscription-1', kind: 'expert_subscription', title: 'Подписка эксперта по работе 151' }
    const { wrapper } = await open(pkg, async (input, init) => { paths.push(String(input)); if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'revision-2' }, package: { ...pkg, version: 2 } }) } return json(String(input).includes('/document-options/') ? page([document]) : String(input).includes('/options/') ? options : pkg) })
    await wrapper.get('[data-edit-issue-package]').trigger('click'); await wrapper.get('[data-add-package-item]').trigger('click'); await flushPromises(); await wrapper.get('[name="item_work_0"]').setValue('work-1'); await wrapper.get('[name="document_search"]').setValue('  Подписка  '); await wrapper.get('[data-find-issue-documents]').trigger('click'); await flushPromises(); await wrapper.get('[name="document_id"]').setValue('subscription-1'); await wrapper.get('[name="package_reason"]').setValue('Добавлена подписка'); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises()
    expect(paths).toContain('/api/v1/issue-packages/package-1/document-options/?kind=expert_subscription&search=%D0%9F%D0%BE%D0%B4%D0%BF%D0%B8%D1%81%D0%BA%D0%B0&page=1'); expect(writes[0]).toEqual({ expected_version: 1, reason: 'Добавлена подписка', materials_description: 'Два тома', note: '', items: [{ kind: 'expert_subscription', expertise_id: 'work-1', document_id: 'subscription-1', note: '' }], billing: [{ expertise_id: 'work-1', is_paid: false }] }); wrapper.unmount()
  })
  it('submits a separate check body and reads readiness from the returned package', async () => {
    const value = { ...pkg, readiness: { ...pkg.readiness, blockers: [], can_check: true } }, writes: unknown[] = []
    const { wrapper } = await open(value, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { expect(String(input)).toBe('/api/v1/issue-packages/package-1/check/'); expect(new Headers(init.headers).get('Idempotency-Key')).toBeTruthy(); writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'check-1' }, package: ready }) } return json(String(input).includes('/options/') ? options : value) })
    await wrapper.get('[data-start-package-check]').trigger('click'); await wrapper.get('[name="issue_command_reason"]').setValue('Состав проверен'); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); expect(writes).toEqual([{ expected_version: 1, reason: 'Состав проверен' }]); expect(wrapper.get('[data-package-state]').text()).toBe('Проверен'); expect(wrapper.get('[data-issue-fact]').text()).toContain('Не выдано'); wrapper.unmount()
  })
  it('records actual issue with explicit date, recipient and basis without implying payment or sending mail', async () => {
    const writes: unknown[] = [], issued = { id: 'issue-1', check_id: 'check-1', issued_on: '2026-10-28', method: options.methods[0]!, recipient_name: 'Представитель суда', recipient_basis: 'Доверенность №7', tracking: '', comment: '', evidence: null, actor, created_at: revision.created_at, reason: 'Фактическая передача' }
    const { wrapper } = await open(ready, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { expect(String(input)).toBe('/api/v1/issue-packages/package-1/issue/'); writes.push(JSON.parse(String(init.body))); return json({ event: { id: 'issue-1' }, package: { ...ready, state: 'issued', version: 2, issuance: issued, allowed_actions: [] } }) } return json(String(input).includes('/document-options/') ? page([]) : String(input).includes('/options/') ? options : ready) })
    await wrapper.get('[data-start-issue]').trigger('click'); expect(wrapper.get('[name="issued_on"]').element).toHaveProperty('value', ''); await wrapper.get('[name="issued_on"]').setValue('2026-10-28'); await wrapper.get('[name="method_id"]').setValue('method-1'); await wrapper.get('[name="recipient_name"]').setValue('  Представитель суда  '); await wrapper.get('[name="recipient_basis"]').setValue('Доверенность №7'); await wrapper.get('[name="issue_command_reason"]').setValue('Фактическая передача'); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises()
    expect(writes).toEqual([{ expected_version: 1, reason: 'Фактическая передача', issued_on: '2026-10-28', method_id: 'method-1', recipient_name: 'Представитель суда', recipient_basis: 'Доверенность №7', tracking: '', comment: '', evidence_document_id: null }]); expect(wrapper.get('[data-issue-fact]').text()).toContain('2026-10-28'); expect(wrapper.find('[data-start-issue]').exists()).toBe(false); wrapper.unmount()
  })
  it('replays the normalized body/key/version after lost issue response and refresh despite current readiness', async () => {
    let version = 1; const writes: { body: string; key: string | null }[] = []
    const { wrapper } = await open(ready, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') } return json({ event: { id: 'same' }, package: { ...ready, version } }) } return json(String(input).includes('/options/') ? options : String(input).includes('/document-options/') ? page([]) : { ...ready, version, allowed_actions: version === 1 ? ready.allowed_actions : [], readiness: version === 1 ? ready.readiness : { ...pkg.readiness, can_issue: false } }) })
    await wrapper.get('[data-start-issue]').trigger('click'); await wrapper.get('[name="issued_on"]').setValue('2026-10-28'); await wrapper.get('[name="method_id"]').setValue('method-1'); await wrapper.get('[name="recipient_name"]').setValue('Получатель'); await wrapper.get('[name="recipient_basis"]').setValue('Доверенность'); await wrapper.get('[name="issue_command_reason"]').setValue('Передача'); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); await wrapper.get('[name="issue_command_reason"]').setValue('  Передача  '); expect(wrapper.get('[data-issue-command] button[type="submit"]').attributes('formnovalidate')).toBeDefined(); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]); wrapper.unmount()
  })
  it('shows accepted check files rather than silently selecting later versions', async () => {
    const first = { id: 'v1', number: 1, original_name: 'accepted.pdf', content_type: 'application/pdf', size: 12, sha256: '', created_at: revision.created_at, download_url: '/v1/download/', preview_url: '/v1/preview/' }
    const document = { ...basis, accepted_version_id: 'v1', versions: [first, { ...first, id: 'v2', number: 2, original_name: 'later.pdf', preview_url: '/v2/preview/' }] }
    const { wrapper } = await open({ ...ready, checks: [{ id: 'check-1', revision_id: 'revision-1', actor, created_at: revision.created_at, reason: 'Проверка', works: [{ expertise_id: 'work-1', closure_id: 'closure-1' }], files: [{ item_id: null, closure_id: 'closure-1', document }] }] }); expect(wrapper.get('[data-package-check-history] iframe').attributes('src')).toBe('/v1/preview/'); wrapper.unmount()
  })
  it('preserves filters in return URLs and guards unsaved package fields', async () => {
    const paths: string[] = []
    const { wrapper } = await open(pkg, async input => { paths.push(String(input)); return json(String(input).includes('/options/') ? options : page([pkg])) }, '/issue-packages?state=needs_recheck&search=151&issued_from=2026-10-01&page=2')
    expect(paths).toContain('/api/v1/issue-packages/?search=151&state=needs_recheck&issued_from=2026-10-01&page=2'); const target = new URL(wrapper.get('[data-open-issue-package]').attributes('href')!, 'http://localhost'); expect(target.searchParams.get('return')).toBe('/issue-packages?state=needs_recheck&search=151&issued_from=2026-10-01&page=2'); wrapper.unmount()
    const opened = await open(); await opened.wrapper.get('[data-edit-issue-package]').trigger('click'); await opened.wrapper.get('[name="materials_description"]').setValue('Несохранённый состав'); vi.spyOn(window, 'confirm').mockReturnValue(false); await opened.router.push('/workspace'); expect(opened.router.currentRoute.value.path).toBe('/issue-packages/package-1'); opened.wrapper.unmount()
  })
  it('guards the module and full package routes while letting the own expert see a restricted minimal status', async () => {
    const paths: string[] = [], pinia = sessionWith('expertise.view'), client = new ApiClient(async input => { paths.push(String(input)); return json({ status: 'issued', issued_on: '2026-10-28', package: { id: 'hidden-package', restricted: true } }) }), router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/expertises', '/issue-packages', '/issue-packages/:id', '/issue-packages/new'].map(path => ({ path, component: { template: '<p />' } })) }); await router.push('/workspace')
    const app = mount(App, { global: { plugins: [pinia, router] } }), home = mount(HomePage, { global: { plugins: [pinia, router] } }), status = mount(ExpertiseIssueStatus, { props: { expertiseId: 'work-1', materialId: 'material-1' }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises(); expect(paths).toEqual([]); expect(status.text()).toBe(''); expect(app.find('nav a[href="/issue-packages"]').exists()).toBe(false)
    useSessionStore().user!.supported_modules = ['issuance']; await flushPromises(); expect(paths).toEqual(['/api/v1/expertises/work-1/issue-status/']); expect(status.text()).toContain('2026-10-28'); expect(status.find('a[href*="hidden-package"]').exists()).toBe(false); expect(home.find('a[href="/issue-packages"]').exists()).toBe(false); app.unmount(); home.unmount(); status.unmount()
    sessionWith('issue.view'); await applicationRouter.push('/issue-packages'); expect(applicationRouter.currentRoute.value.path).toBe('/workspace'); useSessionStore().user!.supported_modules = ['issuance']; await applicationRouter.push('/issue-packages'); expect(applicationRouter.currentRoute.value.path).toBe('/issue-packages')
  })
  it('preserves a staged supplemental file and upload key through lost upload and package conflict', async () => {
    let creates = 0; const uploads: { key: string | null; version: FormDataEntryValue | null }[] = [], writes: Record<string, unknown>[] = []
    const { wrapper } = await open(pkg, async (input, init) => { const path = String(input); if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (path.endsWith('/documents/')) { creates++; expect(JSON.parse(String(init?.body))).toEqual({ kind: 'expert_subscription', title: 'Подписка по работе', source_kind: 'uploaded_copy', department_id: 'd-4' }); return json({ ...basis, id: 'new-subscription', kind: 'expert_subscription', source_kind: 'uploaded_copy', title: 'Подписка по работе' }, 201) } if (path.endsWith('/versions/')) { uploads.push({ key: new Headers(init?.headers).get('Idempotency-Key'), version: (init?.body as FormData).get('expected_version') }); if (uploads.length === 1) throw new TypeError('Ответ файла потерян'); return json({ id: 'v1', number: 1, original_name: 'subscription.pdf', content_type: 'application/pdf', size: 1, sha256: '', created_at: revision.created_at, download_url: '/download/', preview_url: null }, 201) } if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return json({ code: 'version_conflict', message: 'Обновите комплект' }, 409) } return json(path.includes('/document-options/') ? page([]) : path.includes('/options/') ? options : pkg) }, '/issue-packages/package-1', ['issue.view', 'issue.prepare', 'documents.upload'])
    await wrapper.get('[data-edit-issue-package]').trigger('click'); await wrapper.get('[data-add-package-item]').trigger('click'); await wrapper.get('[name="item_work_0"]').setValue('work-1'); await wrapper.get('[name="document_source"]').setValue('new'); await wrapper.get('[name="document_title"]').setValue('Подписка по работе'); await wrapper.get('[name="source_kind"]').setValue('uploaded_copy'); await wrapper.get('[name="package_reason"]').setValue('Документ подготовлен'); Object.defineProperty(wrapper.get('input[type="file"]').element, 'files', { value: [new File(['scan'], 'subscription.pdf')] }); await wrapper.get('input[type="file"]').trigger('change')
    await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises(); expect(writes).toEqual([]); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises(); expect(creates).toBe(1); expect(uploads[1]).toEqual(uploads[0]); expect(writes[0]!.expected_version).toBe(1); expect(writes[0]!.items).toEqual([{ kind: 'expert_subscription', expertise_id: 'work-1', document_id: 'new-subscription', note: '' }]); expect(wrapper.get('[name="document_title"]').element).toHaveProperty('value', 'Подписка по работе'); wrapper.unmount()
  })
  it('retains issue proof after a conflict without rebasing it on refresh or creating a second document', async () => {
    let version = 1, creates = 0; const writes: { body: Record<string, unknown>; key: string | null }[] = []
    const { wrapper } = await open(ready, async (input, init) => { const path = String(input); if (path.endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (path.endsWith('/documents/')) { creates++; return json({ ...basis, id: 'proof-1', kind: 'letter', title: 'Подтверждение передачи' }, 201) } if (init?.method === 'POST') { writes.push({ body: JSON.parse(String(init.body)), key: new Headers(init.headers).get('Idempotency-Key') }); return json({ code: 'version_conflict', message: 'Нужна свежая версия' }, 409) } return json(path.includes('/document-options/') ? page([]) : path.includes('/options/') ? options : { ...ready, version }) }, '/issue-packages/package-1', ['issue.view', 'issue.confirm', 'documents.upload'])
    await wrapper.get('[data-start-issue]').trigger('click'); await wrapper.get('[name="issued_on"]').setValue('2026-10-28'); await wrapper.get('[name="method_id"]').setValue('method-1'); await wrapper.get('[name="recipient_name"]').setValue('Получатель'); await wrapper.get('[name="recipient_basis"]').setValue('Доверенность'); await wrapper.get('[name="issue_command_reason"]').setValue('Передача'); await wrapper.get('[name="document_source"]').setValue('new'); await wrapper.get('[name="proof_department_id"]').setValue('d-4'); await wrapper.get('[name="document_title"]').setValue('Подтверждение передачи'); version = 2; await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises()
    expect(writes[0]!.body.expected_version).toBe(1); expect(writes[0]!.body.evidence_document_id).toBe('proof-1'); await wrapper.get('[data-accept-issue-version]').trigger('click'); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); expect(writes[1]!.body.expected_version).toBe(2); expect(writes[1]!.key).not.toBe(writes[0]!.key); expect(creates).toBe(1); wrapper.unmount()
  })
  it('retains a forbidden issue draft and disables new commands when server actions disappear', async () => {
    let revoked = false, posts = 0
    const { wrapper } = await open(ready, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { posts++; revoked = true; return json({ code: 'forbidden', message: 'Право отозвано' }, 403) } return json(String(input).includes('/document-options/') ? page([]) : String(input).includes('/options/') ? options : { ...ready, allowed_actions: revoked ? [] : ready.allowed_actions }) })
    await wrapper.get('[data-start-issue]').trigger('click'); await wrapper.get('[name="issued_on"]').setValue('2026-10-28'); await wrapper.get('[name="method_id"]').setValue('method-1'); await wrapper.get('[name="recipient_name"]').setValue('Получатель'); await wrapper.get('[name="recipient_basis"]').setValue('Основание'); await wrapper.get('[name="issue_command_reason"]').setValue('Передача'); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); expect(wrapper.get('[name="recipient_name"]').element).toHaveProperty('value', 'Получатель'); expect(wrapper.get('[data-issue-command] button[type="submit"]').attributes('disabled')).toBeDefined(); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); expect(posts).toBe(1); wrapper.unmount()
  })
  it('cancels an obsolete GET after check returns a current package', async () => {
    let resolveLate: ((response: Response) => void) | undefined, gets = 0
    const value = { ...pkg, readiness: { ...pkg.readiness, blockers: [], can_check: true } }
    const { wrapper } = await open(value, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') return json({ event: { id: 'checked' }, package: ready }); if (String(input).includes('/options/')) return json(options); gets++; return gets > 1 ? new Promise<Response>(resolve => { resolveLate = resolve }) : json(value) })
    await wrapper.get('[data-start-package-check]').trigger('click'); await wrapper.get('[name="issue_command_reason"]').setValue('Проверка'); await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); await wrapper.get('[data-issue-command]').trigger('submit'); await flushPromises(); resolveLate!(json(pkg)); await flushPromises(); expect(wrapper.get('[data-package-state]').text()).toBe('Проверен'); wrapper.unmount()
  })
  it('keeps document creation unavailable while package catalog options fail to load', async () => {
    const { wrapper } = await open(pkg, async input => String(input).includes('/options/') ? json({ code: 'catalog_unavailable', message: 'Не удалось загрузить справочники' }, 503) : json(pkg), '/issue-packages/package-1', ['issue.view', 'issue.prepare', 'documents.upload'])
    await wrapper.get('[data-edit-issue-package]').trigger('click'); expect(wrapper.text()).toContain('Не удалось загрузить справочники'); expect(wrapper.get('[data-add-package-item]').attributes('disabled')).toBeDefined(); wrapper.unmount()
  })
  it('recovers catalog loading through an explicit retry without replacing the open draft', async () => {
    let calls = 0
    const { wrapper } = await open(pkg, async input => { if (String(input).includes('/options/')) { calls++; return calls === 1 ? json({ code: 'catalog_unavailable', message: 'Справочники недоступны' }, 503) : json(options) } return json(pkg) })
    await wrapper.get('[data-edit-issue-package]').trigger('click'); await wrapper.get('[name="materials_description"]').setValue('Несохранённые материалы'); await wrapper.get('[data-retry-issue-options]').trigger('click'); await flushPromises(); expect(wrapper.get('[data-add-package-item]').attributes('disabled')).toBeUndefined(); expect(wrapper.get('[name="materials_description"]').element).toHaveProperty('value', 'Несохранённые материалы'); wrapper.unmount()
  })
  it('replays a lost draft response after refresh with the original normalized content and key', async () => {
    let version = 1; const writes: { body: string; key: string | null }[] = []
    const { wrapper } = await open(pkg, async (input, init) => { if (String(input).endsWith('/csrf/')) return json({ csrf_token: 'token' }); if (init?.method === 'POST') { writes.push({ body: String(init.body), key: new Headers(init.headers).get('Idempotency-Key') }); if (writes.length === 1) { version = 2; throw new TypeError('Ответ потерян') } return json({ event: { id: 'revision-same' }, package: { ...pkg, version } }) } return json(String(input).includes('/options/') ? options : { ...pkg, version }) })
    await wrapper.get('[data-edit-issue-package]').trigger('click'); await wrapper.get('[name="materials_description"]').setValue('  Три тома  '); await wrapper.get('[name="package_reason"]').setValue('Редакция'); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises(); await wrapper.get('[data-refresh-issue-package]').trigger('click'); await flushPromises(); await wrapper.get('[name="materials_description"]').setValue('Три тома'); await wrapper.get('[name="package_reason"]').setValue('  Редакция  '); expect(wrapper.get('[data-issue-package-draft] button[type="submit"]').attributes('formnovalidate')).toBeDefined(); await wrapper.get('[data-issue-package-draft]').trigger('submit'); await flushPromises(); expect(writes).toHaveLength(2); expect(writes[1]).toEqual(writes[0]); wrapper.unmount()
  })
  it('gates package controls by server actions and hides data fetching without the capability', async () => {
    const { wrapper } = await open({ ...ready, allowed_actions: [] }); expect(wrapper.find('[data-edit-issue-package]').exists()).toBe(false); expect(wrapper.find('[data-start-package-check]').exists()).toBe(false); expect(wrapper.find('[data-start-issue]').exists()).toBe(false); wrapper.unmount()
    const pinia = sessionWith('issue.view'), paths: string[] = [], client = new ApiClient(async input => { paths.push(String(input)); return json(pkg) }), router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/issue-packages/package-1', component: IssuePackagePage }] }); await router.push('/issue-packages/package-1'); const hidden = mount(IssuePackagePage, { global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises(); expect(paths).toEqual([]); hidden.unmount()
  })
  it('never sends initial creation when the material server response denies preparation', async () => {
    const writes: string[] = []
    const { wrapper } = await open(pkg, async (input, init) => { if (init?.method === 'POST') writes.push(String(input)); return json(String(input).includes('/options/') ? options : { material, package: null, can_prepare: false }) }, '/issue-packages/new?material_id=material-1'); expect(wrapper.find('[data-issue-package-draft]').exists()).toBe(false); expect(wrapper.text()).toContain('Сервер не разрешил подготовку'); expect(writes).toEqual([]); wrapper.unmount()
  })
  it('offers the enabled journal only under issue.view and sends URL filter updates safely', async () => {
    const pinia = sessionWith('issue.view'); useSessionStore().user!.supported_modules = ['issuance']; const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/issue-packages'].map(path => ({ path, component: { template: '<p />' } })) }); await router.push('/workspace'); const app = mount(App, { global: { plugins: [pinia, router] } }), home = mount(HomePage, { global: { plugins: [pinia, router] } }); expect(app.find('nav a[href="/issue-packages"]').exists()).toBe(true); expect(home.find('a[href="/issue-packages"]').exists()).toBe(true); app.unmount(); home.unmount()
    const opened = await open(pkg, async () => json(page([])), '/issue-packages?state=draft&page=2'); await opened.wrapper.get('[name="issue_search"]').setValue('Суд'); await opened.wrapper.get('form.toolbar').trigger('submit'); await flushPromises(); expect(opened.router.currentRoute.value.query).toEqual({ search: 'Суд', state: 'draft', page: '1' }); opened.wrapper.unmount()
    const details = await open(pkg, undefined, '/issue-packages/package-1?return=//example.test/'); expect(details.wrapper.get('[data-back-to-issue-packages]').attributes('href')).toBe('/issue-packages'); details.wrapper.unmount()
  })
  it('renders historical records whose actor is unknown without fabricating a person', async () => {
    const historical = { ...revision, actor: null }
    const { wrapper } = await open({ ...pkg, content: historical, content_history: [historical], checks: [{ id: 'old-check', revision_id: revision.id, actor: null, created_at: revision.created_at, reason: 'Прежняя проверка', works: [], files: [] }], issuance: { id: 'old-issue', check_id: 'old-check', issued_on: '2026-10-28', method: options.methods[0]!, recipient_name: 'Суд', recipient_basis: 'Основание', tracking: '', comment: '', evidence: null, actor: null, created_at: revision.created_at, reason: 'Прежняя выдача' } })
    expect(wrapper.get('[data-package-check-history]').text()).toContain('Сотрудник не указан'); expect(wrapper.text()).toContain('Прежняя выдача'); wrapper.unmount()
  })
  it('does not offer a preparation shortcut into a package marked restricted', async () => {
    const pinia = sessionWith('expertise.view', 'issue.view', 'issue.prepare'); useSessionStore().user!.supported_modules = ['issuance']; const router = createRouter({ history: createMemoryHistory(), routes: ['/workspace', '/issue-packages/new'].map(path => ({ path, component: { template: '<p />' } })) }); await router.push('/workspace')
    const client = new ApiClient(async () => json({ status: 'not_issued', issued_on: null, package: { id: 'hidden-package', restricted: true } })); const wrapper = mount(ExpertiseIssueStatus, { props: { expertiseId: 'work-1', materialId: material.id }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } }); await flushPromises(); expect(wrapper.find('[data-open-material-package]').exists()).toBe(false); expect(wrapper.text()).toContain('Доступ к полному комплекту ограничен'); wrapper.unmount()
  })
})
