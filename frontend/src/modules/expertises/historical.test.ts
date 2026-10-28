import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../../api/client'
import { json, page, sessionWith } from '../../test/fixtures'
import { expertise, receipt, testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'
import ExpertisesPage from './ExpertisesPage.vue'
import ReceiptPage from '../intake/ReceiptPage.vue'
import IntakePage from '../intake/IntakePage.vue'
import ExpertiseIssueStatus from '../issuance/ExpertiseIssueStatus.vue'
import { useSessionStore } from '../../stores/session'

const history = {
  id: 'history-1', operational: false, complex_known: false, composition_known: false,
  suspension_history_complete: false, statistics_confirmed: false,
  result_kind: 'expert_conclusion', completed_on: '2026-10-06', return_decided_on: null, issued_on: null,
  complexity_level: null, questions: 2, categorical: 2, probable: 0, unresolved: 0, amount: null,
  authority_type: 'Тип органа в источнике', authority_name: 'Орган из журнала', official: '', contact: '',
  basis_text: 'Сведения о постановлении в журнале', case_description: 'Описание из источника', inventory: 'Опись из журнала',
  executor_raw: 'Фамилия в исходной ячейке', unresolved_note: '', unresolved_reason_raw: '', notes: '', delivery: '',
  current_participants: [{ id: 'old-employee', full_name: 'Подтверждённый участник истории' }],
  source: { batch_id: 'batch-1', row_id: 'row-1', source_row: 155, origin_url: null, source_observed_at: '2026-10-28T00:00:00Z' },
  report_gaps: [{ code: 'pause_history_unknown', field: 'suspensions', message: 'История приостановок не подтверждена.' }],
}
const historical = {
  ...expertise, origin_kind: 'historical', historical: history, specialty: null, appointment_nature: null, is_commission: null,
  state: 'completed', allowed_actions: [], basis_document: null,
  receipt: { ...expertise.receipt, status: 'historical' },
  production: { ...expertise.production, calendar_days: 6, counted_through: '2026-10-06', paused_days: null, active_calendar_days: null },
}

describe('historical works in the main registry', () => {
  it('names source issue evidence and does not offer to prepare a second package', async () => {
    const router = await testRouter('/expertises/work-1')
    const pinia = sessionWith('expertise.view', 'issue.view', 'issue.prepare')
    useSessionStore(pinia).user!.supported_modules = ['issuance']
    const client = new ApiClient(async () => json({ status: 'issued', issued_on: '2026-10-10', fact_origin: 'historical', package: null }))
    const wrapper = mount(ExpertiseIssueStatus, { props: { expertiseId: 'work-1', materialId: 'material-1' }, global: { plugins: [pinia, router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Историческая отметка выдачи')
    expect(wrapper.text()).toContain('2026-10-10')
    expect(wrapper.find('[data-open-material-package]').exists()).toBe(false)
    wrapper.unmount()
  })
  it.each(['detail', 'list'])('does not advertise historical intake as a native draft: %s', async view => {
    const router = await testRouter(view === 'detail' ? '/receipts/receipt-1' : '/intake')
    const importedReceipt = { ...receipt, status: 'historical', basis_document: null }
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/references/')) return json(page([]))
      return json(view === 'detail' ? importedReceipt : page([importedReceipt]))
    })
    const wrapper = mount(view === 'detail' ? ReceiptPage : IntakePage, { global: { plugins: [sessionWith('receipts.view', 'receipts.accept', 'receipts.amend', 'expertise.register'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Историческое поступление')
    expect(wrapper.text()).not.toContain('Черновик')
    expect(wrapper.findAll('button').some(button => button.text() === 'Уточнить поступление')).toBe(false)
    expect(wrapper.find('[data-accept-receipt]').exists()).toBe(false)
    expect(wrapper.find('[data-register-expertise]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('shows unknown composition and specialty rather than inventing a new registration or assignment', async () => {
    const router = await testRouter('/expertises/work-1')
    const client = new ApiClient(async () => json(historical))
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view', 'expertise.assign'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Специальность не уточнена')
    expect(wrapper.text()).toContain('Характер назначения не уточнён')
    expect(wrapper.text()).toContain('Состав не уточнён')
    expect(wrapper.get('[data-historical-facts]').text()).toContain('Фамилия в исходной ячейке')
    expect(wrapper.get('[data-historical-facts]').text()).toContain('Подтверждённый участник истории')
    expect(wrapper.get('[data-current-assignments]').text()).not.toContain('Подтверждённый участник истории')
    expect(wrapper.find('[data-start-assignment]').exists()).toBe(false)
    expect(wrapper.find('iframe').exists()).toBe(false)
    expect(wrapper.get('[data-paused-days]').text()).toBe('Неизвестно')
    expect(wrapper.get('[data-suspension-history]').text()).toContain('Полнота исторических приостановок неизвестна')
    wrapper.unmount()
  })

  it('keeps actual zero separate from missing facts and does not offer a restricted source link', async () => {
    const router = await testRouter('/expertises/work-1')
    const client = new ApiClient(async () => json({ ...historical, specialty: expertise.specialty, historical: { ...history, issued_on: '2026-10-10' } }))
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.get('[data-history-probable]').text()).toBe('0')
    expect(wrapper.get('[data-history-complexity]').text()).toBe('Неизвестно')
    expect(wrapper.get('[data-history-issued]').text()).toContain('2026-10-10')
    expect(wrapper.get('[data-historical-facts]').text()).toContain('не подтверждает новый электронный комплект')
    expect(wrapper.find('[data-history-source-link]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('lists a registration with no known specialty without excluding it or calling it additional', async () => {
    const router = await testRouter('/expertises')
    const client = new ApiClient(async input => {
      const path = String(input)
      if (path.includes('/references/')) return json(page([]))
      if (path.includes('filter-options')) return json({ employees: [] })
      return json(page([historical]))
    })
    const wrapper = mount(ExpertisesPage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.get('[data-open-expertise]').text()).toContain('151/4-1-26')
    expect(wrapper.text()).toContain('Специальность не уточнена')
    expect(wrapper.text()).toContain('Характер не уточнён')
    expect(wrapper.text()).not.toContain('Дополнительная')
    expect(wrapper.text()).toContain('Подтверждённый участник истории')
    wrapper.unmount()
  })

  it('clears historical source facts when navigating to another work before its reply', async () => {
    let resolveNew!: (value: Response) => void
    const next = new Promise<Response>(resolve => { resolveNew = resolve })
    const client = new ApiClient(async input => String(input).includes('work-2') ? next : json({ ...historical, specialty: expertise.specialty }))
    const router = await testRouter('/expertises/work-1')
    const wrapper = mount(ExpertisePage, { global: { plugins: [sessionWith('expertise.view'), router], provide: { [apiKey as symbol]: client } } })
    await flushPromises()
    expect(wrapper.text()).toContain('Фамилия в исходной ячейке')
    await router.push('/expertises/work-2'); await flushPromises()
    expect(wrapper.text()).not.toContain('Фамилия в исходной ячейке')
    resolveNew(json({ ...expertise, id: 'work-2' })); await flushPromises()
    expect(wrapper.find('[data-historical-facts]').exists()).toBe(false)
    wrapper.unmount()
  })
})
