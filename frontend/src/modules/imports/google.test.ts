import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter,RouterView } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
import GooglePreview from './GooglePreview.vue'
import ImportPreviewsPage from './ImportPreviewsPage.vue'
import ImportPreviewPage from './ImportPreviewPage.vue'

const source={configured:true,spreadsheet_id:'DEMO_sheet_123',gid:'0',sheet_name:'Лист1',label:'',url:'https://docs.google.com/spreadsheets/d/DEMO_sheet_123/edit#gid=0'}
const batch={id:'batch-google',source_name:'Google-journal.csv',source_kind:'csv',source_origin:'google_csv',origin_url:source.url,source_observed_at:'2026-10-28T00:00:00Z',date_system:'1900',source_sha256:'abc',sheet_name:'Лист1',parser_version:'journal-2026-v1',created_at:'2026-10-28T00:00:00Z',actor:null,row_count:472,summary:{row_count:472,error_rows:0,warning_rows:0,diagnostic_counts:{},state_counts:{}},version:1,apply_available:false,source_url:'/api/v1/imports/batch-google/source/'}
type Transport=ConstructorParameters<typeof ApiClient>[0]
async function open(transport?:Transport,codes=['imports.results.view','imports.preview'],capability=true,component:unknown=GooglePreview,url='/imports'){
  const pinia=sessionWith(...codes);useSessionStore().user!.supported_modules=capability?['journal_import_preview','journal_google_preview']:['journal_import_preview']
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/imports',component:component as never,props:component===GooglePreview?{canCreate:codes.includes('imports.preview')}:false},{path:'/imports/:id',component:ImportPreviewPage},{path:'/workspace',component:{template:'<p>Рабочее место</p>'}}]});await router.push(url)
  const api=new ApiClient(transport??(async()=>json(source)))
  const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}});await flushPromises();return {wrapper,router,pinia}
}
afterEach(()=>vi.restoreAllMocks());enableAutoUnmount(afterEach)

it('reads only the configured Google source with a captured reason and idempotency key',async()=>{
  const writes:{path:string;body:unknown;key:string|null}[]=[]
  const {wrapper}=await open(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'})
    if(init?.method==='POST'){writes.push({path:String(input),body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')});return json({event:{id:'event-google'},batch},201)}return json(source)
  })
  expect(wrapper.text()).toContain('Лист1');expect(wrapper.text()).toContain('Только чтение')
  await wrapper.get('[data-read-google]').trigger('click');await wrapper.get('[name="google_reason"]').setValue('  Проверка актуального листа  ');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises()
  expect(writes).toHaveLength(1);expect(writes[0]).toEqual({path:'/api/v1/imports/google-preview/',body:{reason:'Проверка актуального листа',spreadsheet_id:'DEMO_sheet_123',gid:'0'},key:expect.any(String)})
  expect(wrapper.findComponent(GooglePreview).emitted('created')?.[0]?.[0]).toEqual(batch)
})
it('retries a lost reply with exactly the original source, reason and key',async()=>{
  const attempts:{body:string;key:string|null}[]=[]
  const {wrapper}=await open(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'})
    if(init?.method==='POST'){attempts.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});if(attempts.length===1)throw new TypeError('Ответ потерян');return json({event:{id:'event-google'},batch},201)}return json(source)
  })
  await wrapper.get('[data-read-google]').trigger('click');await wrapper.get('[name="google_reason"]').setValue('Повтор');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises()
  expect(wrapper.text()).toContain('Ответ не получен');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises();expect(attempts).toHaveLength(2);expect(attempts[1]).toEqual(attempts[0])
})
it('starts a new attempt after an explicit reason change instead of reusing the rejected body',async()=>{
  const attempts:{body:string;key:string|null}[]=[]
  const {wrapper}=await open(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'})
    if(init?.method==='POST'){attempts.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});return json({code:'invalid_source',message:'Источник недоступен',field_errors:{}},400)}return json(source)
  })
  await wrapper.get('[data-read-google]').trigger('click');await wrapper.get('[name="google_reason"]').setValue('Первое');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises();await wrapper.get('[name="google_reason"]').setValue('Второе');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises()
  expect(attempts).toHaveLength(2);expect(attempts[1]!.key).not.toBe(attempts[0]!.key);expect(JSON.parse(attempts[1]!.body).reason).toBe('Второе')
})
it.each([403,409])('keeps the selected source and reason after %s without silently rereading configuration',async status=>{
  const reads:string[]=[]
  const {wrapper}=await open(async(input,init)=>{if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'});if(init?.method==='POST')return json({code:'command_conflict',message:'Обновите источник',field_errors:{}},status);reads.push(String(input));return json(source)})
  await wrapper.get('[data-read-google]').trigger('click');await wrapper.get('[name="google_reason"]').setValue('Сохранить выбор');await wrapper.get('[data-google-preview-form]').trigger('submit');await flushPromises()
  expect(wrapper.get('[name="google_reason"]').element).toHaveProperty('value','Сохранить выбор');expect(wrapper.text()).toContain('Лист1');expect(reads).toEqual(['/api/v1/imports/google-source/']);expect(wrapper.findComponent(GooglePreview).emitted('created')).toBeUndefined()
})
it('does not read or advertise Google when the module is not supported',async()=>{
  const reads:string[]=[];const {wrapper}=await open(async input=>{reads.push(String(input));return json(source)},undefined,false)
  expect(reads).toEqual([]);expect(wrapper.find('[data-read-google]').exists()).toBe(false)
})
it('shows source information without creation controls to a read-only source reader',async()=>{
  const {wrapper}=await open(undefined,['imports.results.view'])
  expect(wrapper.text()).toContain('Лист1');expect(wrapper.find('[data-read-google]').exists()).toBe(false)
})
it('does not offer a Google read when no source is configured',async()=>{
  const {wrapper}=await open(async()=>json({configured:false}))
  expect(wrapper.text()).toContain('не настроен');expect(wrapper.find('[data-read-google]').exists()).toBe(false)
})
it('protects a prepared Google request when navigation is declined',async()=>{
  const {wrapper,router}=await open();await wrapper.get('[data-read-google]').trigger('click');await wrapper.get('[name="google_reason"]').setValue('Не потерять');vi.spyOn(window,'confirm').mockReturnValue(false);await router.push('/workspace')
  expect(router.currentRoute.value.path).toBe('/imports');expect(wrapper.get('[name="google_reason"]').element).toHaveProperty('value','Не потерять')
})
it('keeps file upload available when the Google source read fails',async()=>{
  const {wrapper}=await open(async input=>String(input).includes('/google-source/')?json({code:'validation_error',message:'Google недоступен',field_errors:{}},400):json(page([])),undefined,true,ImportPreviewsPage)
  expect(wrapper.text()).toContain('Google недоступен');await wrapper.get('[data-new-import-preview]').trigger('click');expect(wrapper.find('input[type="file"]').exists()).toBe(true)
})
it('labels a stored Google snapshot as values rather than workbook formulas',async()=>{
  const {wrapper}=await open(async input=>json(String(input).includes('/rows/')?page([]):batch),undefined,true,ImportPreviewsPage,'/imports/batch-google')
  expect(wrapper.get('[data-google-provenance]').text()).toContain('значений');expect(wrapper.get('[data-google-provenance]').text()).toContain('формулы');expect(wrapper.get('[data-google-provenance]').text()).toContain('28.10.2026')
})
