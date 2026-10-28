import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
enableAutoUnmount(afterEach)
it('shows the selected-year server plan and links plan gaps without substituting a hardcoded total',async()=>{
 const live={...result,year:2027,from:'2027-01-01',to:'2027-10-31',plan_summary:{id:'annual',year:2027,total:10,version:2,basis_text:'Утверждённый план нового года',document_id:null,known_sum:7,unallocated:3,line_count:2,known_line_count:2,unknown_line_count:0},source:{type:'registry',id:null,name:'АИС',row_count:0,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},cells:[],gaps:[{code:'planAllocation',sections:[6],message:'Не распределено3',fields:'plan.lines',rows:[],plan_year:2027}]}
 const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports');await wrapper.get('[name="year"]').setValue('2027');await wrapper.get('form').trigger('submit');await flushPromises()
 const summary=wrapper.get('[data-report-plan]');expect(summary.text()).toContain('10');expect(summary.text()).toContain('редакция 2');expect(summary.text()).toContain('Утверждённый план нового года')
 expect(summary.get('a').attributes('href')).toBe('/report-plans?year=2027');expect(wrapper.get('.report-gap a').attributes('href')).toBe('/report-plans?year=2027');expect(wrapper.text()).not.toContain('План 2026 — 294')
 await wrapper.get('[name="year"]').setValue('2028');expect(wrapper.find('[data-report-plan]').exists()).toBe(false)
})
it('selects a counting policy, labels the server result and discards an obsolete mode response',async()=>{
 const paths:string[]=[];let resolve!:(value:Response)=>void;let pending=false
 const live={...result,delay_reason_policy:'all',source:{type:'registry',id:null,name:'АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},cells:[],gaps:[]}
 const {wrapper}=await open(async input=>{paths.push(String(input));return pending?new Promise<Response>(r=>{resolve=r}):json({...live,delay_reason_policy:String(input).includes('delay_reason_policy=primary')?'primary':'all'})},['expertise.view','reports.form151.run','reports.form151.download'],'/reports')
 expect(wrapper.get('[name="delay_reason_policy"]').element).toHaveProperty('value','all')
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(paths.at(-1)).toContain('delay_reason_policy=all')
 expect(wrapper.get('[data-result-delay-policy]').text()).toContain('По всем указанным причинам')
 await wrapper.get('[name="delay_reason_policy"]').setValue('primary');expect(wrapper.find('[data-report-result]').exists()).toBe(false)
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(paths.at(-1)).toContain('delay_reason_policy=primary');expect(wrapper.get('[data-result-delay-policy]').text()).toContain('Только по основной причине')
 pending=true;await wrapper.get('form').trigger('submit');await flushPromises()
 await wrapper.get('[name="delay_reason_policy"]').setValue('all');resolve(json({...live,delay_reason_policy:'primary'}));await flushPromises()
 expect(wrapper.find('[data-report-result]').exists()).toBe(false);expect(wrapper.find('[data-download-report]').exists()).toBe(false)
})
it('does not offer or send a delay policy for a source snapshot',async()=>{
 const paths:string[]=[]
 const {wrapper}=await open(async input=>{paths.push(String(input));return json(String(input).includes('/imports/')?page([batch]):result)})
 expect(wrapper.find('[name="delay_reason_policy"]').exists()).toBe(false)
 await wrapper.get('form').trigger('submit');await flushPromises()
 expect(paths.at(-1)).not.toContain('delay_reason_policy');expect(wrapper.find('[data-result-delay-policy]').exists()).toBe(false)
})
const batch={id:'batch-1',source_name:'Журнал Google',source_origin:'google_csv',created_at:'2026-10-28T00:00:00Z',row_count:472,sheet_name:'Лист1',source_sha256:'abc'}
const result={status:'preliminary',version:'v1',year:2026,month:9,from:'2026-01-01',to:'2026-09-30',source:{id:'batch-1',name:'Журнал Google',sha256:'abc',row_count:472,created_at:batch.created_at},download_url:'/api/v1/reports/form151/xlsx/?batch_id=batch-1&year=2026&month=9',cells:[{sheet:'Раздел 1',address:'J108',value:321,rows:[4]}],section_coverage:[{section:1,filled:10,unavailable:2,status:'Частично'}],gaps:[{code:'dates',sections:[1],message:'Не указана дата окончания',fields:'P',rows:[4]}]}
async function open(transport:typeof fetch,actions=['imports.results.view','reports.form151.run','reports.form151.download'],initial='/reports?batch_id=batch-1'){
  const component=(await import('./ReportsPage.vue')).default
  const pinia=sessionWith(...actions),router=createRouter({history:createMemoryHistory(),routes:[{path:'/reports',component},{path:'/report-plans',component:{template:'<p>Планы</p>'}},{path:'/imports',component:{template:'<p>Источники</p>'}},{path:'/imports/:id',component:{template:'<p>Снимок</p>'}},{path:'/expertises',component:{template:'<p>Реестр</p>'}},{path:'/expertises/:id',component:{template:'<p>Карточка</p>'}}]})
  await router.push(initial);await router.isReady()
  const wrapper=mount(component,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:new ApiClient(transport)}}})
  await flushPromises();return {wrapper,pinia}
}
it('renders server totals and a download only after the selected calculation',async()=>{
  const paths:string[]=[]
  const {wrapper}=await open(async input=>{paths.push(String(input));return json(String(input).includes('/imports/')?page([batch]):result)})
  expect(wrapper.find('[data-download-report]').exists()).toBe(false)
  await wrapper.get('[name="month"]').setValue('9');await wrapper.get('form').trigger('submit');await flushPromises()
  expect(paths.at(-1)).toContain('batch_id=batch-1&year=2026&month=9')
  expect(wrapper.text()).toContain('321');expect(wrapper.text()).toContain('Не указана дата окончания')
  expect(wrapper.get('[data-download-report]').attributes('disabled')).toBeUndefined()
  await wrapper.get('[name="month"]').setValue('10');await flushPromises()
  expect(wrapper.find('[data-download-report]').exists()).toBe(false)
})
it('defaults to live registry without requesting snapshots and links work provenance',async()=>{
  const paths:string[]=[]
  const live={...result,source:{type:'registry',name:'Рабочая база АИС',row_count:472,excluded_demo_count:6,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc'},records:{'work-1':{id:'work-1',registration_number:'151/1-1-26'}},cells:[{sheet:'Раздел 1',address:'J108',value:1,rows:['work-1']}],gaps:[{code:'dates',sections:[1],message:'Нужно уточнение',fields:'completed_on',rows:['work-1']}]}
  const {wrapper}=await open(async input=>{paths.push(String(input));return json(live)},['expertise.view','reports.form151.run'],'/reports')
  expect(wrapper.find('[name="batch_id"]').exists()).toBe(false)
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(paths).toHaveLength(1);expect(paths[0]).toContain('source=registry')
  expect(wrapper.text()).toContain('Учебных работ исключено: 6')
  expect(wrapper.find('a[href="/expertises/work-1"]').exists()).toBe(true)
})
it('shows the explicit 3214 cell and provenance from case metadata in registry mode',async()=>{
 const live={...result,source:{type:'registry',id:null,name:'Рабочая база АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'test',excluded_demo_count:0},records:{'work-1':{id:'work-1',registration_number:'151/1-1-26'}},cells:[{sheet:'Раздел 1',address:'P108',value:1,rows:['work-1']}]}
 const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports');await wrapper.get('form').trigger('submit');await flushPromises()
 expect(wrapper.findAll('th').map(c=>c.text())).toContain('В рамках 3214-р');expect(wrapper.text()).not.toContain('повторность и 3214-р ещё не рассчитываются')
 expect(wrapper.findAll('td').some(td=>td.find('button.report-number').exists()&&td.get('button.report-number').text()==='1'&&td.attributes('title')?.includes('151/1-1-26'))).toBe(true)
})
it('invalidates registry result when switching source mode and does not save a download error',async()=>{
  const {wrapper}=await open(async input=>String(input).includes('/imports/')?json(page([batch])):String(input).includes('/xlsx/')?json({code:'command_conflict',message:'Данные изменились. Пересчитайте.'},409):json(result),['expertise.view','imports.results.view','reports.form151.run','reports.form151.download'],'/reports')
  await wrapper.get('form').trigger('submit');await flushPromises()
  await wrapper.get('[data-download-report]').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('Данные изменились. Пересчитайте.')
  await wrapper.get('[name="report_source"]').setValue('journal');await flushPromises()
  expect(wrapper.find('[data-report-result]').exists()).toBe(false)
})
it('ignores an obsolete response after period change and requires download grant',async()=>{
  let resolve!:(value:Response)=>void
  const {wrapper,pinia}=await open(async input=>String(input).includes('/imports/')?json(page([batch])):new Promise<Response>(r=>{resolve=r}))
  await wrapper.get('form').trigger('submit');await flushPromises()
  await wrapper.get('[name="opening_balances_complete"]').setValue(true)
  resolve(json(result));await flushPromises()
  expect(wrapper.find('[data-report-result]').exists()).toBe(false)
  useSessionStore(pinia).user!.access['reports.form151.download']=[]
  await wrapper.get('form').trigger('submit');await flushPromises();resolve(json(result));await flushPromises()
  expect(wrapper.find('[data-report-result]').exists()).toBe(true)
  expect(wrapper.find('[data-download-report]').exists()).toBe(false)
})
it('does not request institution source when required access is absent',async()=>{
  const fetcher=vi.fn(async()=>json(page([batch])))
  const {wrapper}=await open(fetcher,['reports.form151.run'])
  expect(fetcher).not.toHaveBeenCalled();expect(wrapper.find('form').exists()).toBe(false)
})

it('shows accepted reason columns and links their contributing work in registry',async()=>{
  const live={...result,source:{type:'registry',id:null,name:'Рабочая база АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},records:{'work-reason':{id:'work-reason',registration_number:'468/4-6-26'}},cells:[
    {sheet:'Раздел 1',address:'G108',value:1,rows:['work-reason']},
    {sheet:'Раздел 2',address:'J107',value:2,rows:['work-reason']},
    {sheet:'Раздел 4',address:'S107',value:1,rows:['work-reason']}],gaps:[]}
  const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports')
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.findAll('th').map(c=>c.text())).toContain('СНДЗ: вне специальных знаний')
  await wrapper.get('tbody .report-number').trigger('click');await flushPromises()
  expect(wrapper.get('a[href="/expertises/work-reason"]').text()).toBe('468/4-6-26')
  await wrapper.findAll('button').find(b=>b.text()==='2. Вопросы')!.trigger('click')
  expect(wrapper.findAll('th').map(c=>c.text())).toContain('Недостаточность материалов')
  expect(wrapper.get('tbody .report-number').text()).toBe('2')
  await wrapper.findAll('button').find(b=>b.text()==='4. Сложность и возвраты')!.trigger('click')
  expect(wrapper.findAll('th').map(c=>c.text())).toContain('По запросу назначившего органа')
  expect(wrapper.text()).not.toContain('Графы причин, повторности и 3214-р ещё не рассчитываются')
})

it('shows unknown reason as a dash with a concrete card gap, not zero',async()=>{
  const live={...result,source:{type:'registry',id:null,name:'Рабочая база АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},records:{'work-unknown':{id:'work-unknown',registration_number:'151/1-1-26'}},cells:[{sheet:'Раздел 1',address:'H108',value:null,rows:['work-unknown']}],gaps:[{code:'sndzReason',sections:[1],message:'Не определена причина полного СНДЗ.',fields:'sndz_reason',rows:['work-unknown']}]}
  const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports')
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.findAll('th').map(c=>c.text())).toContain('СНДЗ: материалы непригодны / недостаточны, отказано в дополнении')
  expect(wrapper.get('tbody .report-number').text()).toBe('—')
  expect(wrapper.get('.report-gap').text()).toContain('Не определена причина полного СНДЗ.')
  expect(wrapper.get('a[href="/expertises/work-unknown"]').text()).toBe('151/1-1-26')
})

it('does not advertise structured reason totals for journal snapshots',async()=>{
  const {wrapper}=await open(async input=>json(String(input).includes('/imports/')?page([batch]):result))
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.findAll('th').map(c=>c.text())).not.toContain('СНДЗ: вне специальных знаний')
  expect(wrapper.text()).toContain('Графы причин, повторности и 3214-р ещё не рассчитываются')
})

it('shows all repeat columns and the actual server rule, keeps cell provenance and clears stale explanations',async()=>{
 const live={...result,rules_version:'rules-test',column_rules:[{section:4,column:'H',official_column:5,meaning:'Правило сервера: одна повторная работа один раз',unit:'работа',period:'По подтверждённой дате окончания',sources:['appointment_nature','WorkClosure.ended_on'],unknown:['Характер не подтверждён'],limitations:['Правило полного СНДЗ не установлено']}],source:{type:'registry',id:null,name:'Рабочая база АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},records:{'work-repeat':{id:'work-repeat',registration_number:'333/3-5-26'}},cells:[{sheet:'Раздел 4',address:'H107',value:1,rows:['work-repeat']}],gaps:[]}
 const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports');await wrapper.get('form').trigger('submit');await flushPromises()
 await wrapper.findAll('button').find(b=>b.text()==='4. Сложность и возвраты')!.trigger('click')
 expect(wrapper.findAll('th').map(c=>c.text())).toContain('Повторных всего')
 await wrapper.get('[data-column-rule="4-H"]').trigger('click');const rule=wrapper.get('[data-report-rule]')
 expect(rule.text()).toContain('Правило сервера: одна повторная работа один раз');expect(rule.text()).toContain('Графа 5');expect(rule.text()).toContain('WorkClosure.ended_on');expect(rule.text()).toContain('Правило полного СНДЗ не установлено')
 await wrapper.get('tbody .report-number').trigger('click');expect(wrapper.get('a[href="/expertises/work-repeat"]').text()).toBe('333/3-5-26')
 await wrapper.get('[name="month"]').setValue('9');expect(wrapper.find('[data-report-rule]').exists()).toBe(false)
})

it('does not invent explanations when the server returned an older contract',async()=>{
 const {wrapper}=await open(async input=>json(String(input).includes('/imports/')?page([batch]):result))
 await wrapper.get('form').trigger('submit');await flushPromises();await wrapper.get('[data-column-rule="1-J"]').trigger('click')
 expect(wrapper.get('[data-report-rule]').text()).toContain('Сервер не вернул правило этой графы');expect(wrapper.get('[data-report-rule]').text()).not.toContain('WorkClosure')
})
it('shows timing reasons and confirmed communication/assessment with the server explanation',async()=>{
 const live={...result,source:{type:'registry',id:null,name:'Рабочая база АИС',row_count:1,calculated_at:'2026-10-28T03:00:00Z',data_revision:'abc',excluded_demo_count:0},records:{'work-timing':{id:'work-timing',registration_number:'333/3-5-26'}},cells:[{sheet:'Раздел 3',address:'M107',value:1,rows:['work-timing']}],column_rules:[{section:3,column:'M',official_column:10,meaning:'Оба факта отправки подтверждены',unit:'работа',period:'По окончанию',sources:['notification_sent','extension_requested'],unknown:['Неизвестны даты'],limitations:['Запрос не означает отправку']}],gaps:[]}
 const {wrapper}=await open(async()=>json(live),['expertise.view','reports.form151.run'],'/reports');await wrapper.get('form').trigger('submit');await flushPromises();await wrapper.findAll('button').find(b=>b.text()==='3. Сроки')!.trigger('click')
 expect(wrapper.findAll('th').map(c=>c.text())).toContain('Сложность исследований');expect(wrapper.findAll('th').map(c=>c.text())).toContain('Подтверждённое нарушение срока')
 await wrapper.get('[data-column-rule="3-M"]').trigger('click');expect(wrapper.get('[data-report-rule]').text()).toContain('Оба факта отправки подтверждены');await wrapper.get('tbody .report-number').trigger('click');expect(wrapper.get('a[href="/expertises/work-timing"]').text()).toBe('333/3-5-26')
})
