import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
enableAutoUnmount(afterEach)
const batch={id:'batch-1',source_name:'Журнал Google',source_origin:'google_csv',created_at:'2026-10-28T00:00:00Z',row_count:472,sheet_name:'Лист1',source_sha256:'abc'}
const result={status:'preliminary',version:'v1',year:2026,month:9,from:'2026-01-01',to:'2026-09-30',source:{id:'batch-1',name:'Журнал Google',sha256:'abc',row_count:472,created_at:batch.created_at},download_url:'/api/v1/reports/form151/xlsx/?batch_id=batch-1&year=2026&month=9',cells:[{sheet:'Раздел 1',address:'J108',value:321,rows:[4]}],section_coverage:[{section:1,filled:10,unavailable:2,status:'Частично'}],gaps:[{code:'dates',sections:[1],message:'Не указана дата окончания',fields:'P',rows:[4]}]}
async function open(transport:typeof fetch,actions=['imports.results.view','reports.form151.run','reports.form151.download']){
  const component=(await import('./ReportsPage.vue')).default
  const pinia=sessionWith(...actions),router=createRouter({history:createMemoryHistory(),routes:[{path:'/reports',component},{path:'/imports',component:{template:'<p>Источники</p>'}},{path:'/imports/:id',component:{template:'<p>Снимок</p>'}}]})
  await router.push('/reports');await router.isReady()
  const wrapper=mount(component,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:new ApiClient(transport)}}})
  await flushPromises();return {wrapper,pinia}
}
it('renders server totals and a download only after the selected calculation',async()=>{
  const paths:string[]=[]
  const {wrapper}=await open(async input=>{paths.push(String(input));return json(String(input).includes('/imports/')?page([batch]):result)})
  await wrapper.get('[name="month"]').setValue('9');await wrapper.get('form').trigger('submit');await flushPromises()
  expect(paths.at(-1)).toContain('batch_id=batch-1&year=2026&month=9')
  expect(wrapper.text()).toContain('321');expect(wrapper.text()).toContain('Не указана дата окончания')
  expect(wrapper.get('[data-download-report]').attributes('href')).toBe(result.download_url)
  await wrapper.get('[name="month"]').setValue('10');await flushPromises()
  expect(wrapper.find('[data-download-report]').exists()).toBe(false)
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
