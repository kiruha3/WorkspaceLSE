import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
enableAutoUnmount(afterEach)
const batch={id:'batch-1',source_name:'Журнал Google',source_origin:'google_csv',created_at:'2026-10-28T00:00:00Z',row_count:472,sheet_name:'Лист1',source_sha256:'abc'}
const result={status:'preliminary',version:'v1',year:2026,month:9,from:'2026-01-01',to:'2026-09-30',source:{id:'batch-1',name:'Журнал Google',sha256:'abc',row_count:472,created_at:batch.created_at},download_url:'/api/v1/reports/form151/xlsx/?batch_id=batch-1&year=2026&month=9',cells:[{sheet:'Раздел 1',address:'J108',value:321,rows:[4]}],section_coverage:[{section:1,filled:10,unavailable:2,status:'Частично'}],gaps:[{code:'dates',sections:[1],message:'Не указана дата окончания',fields:'P',rows:[4]}]}
async function open(transport:typeof fetch,actions=['imports.results.view','reports.form151.run','reports.form151.download'],initial='/reports?batch_id=batch-1'){
  const component=(await import('./ReportsPage.vue')).default
  const pinia=sessionWith(...actions),router=createRouter({history:createMemoryHistory(),routes:[{path:'/reports',component},{path:'/imports',component:{template:'<p>Источники</p>'}},{path:'/imports/:id',component:{template:'<p>Снимок</p>'}}]})
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
