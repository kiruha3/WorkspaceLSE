import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter,RouterView } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
import ImportPreviewsPage from './ImportPreviewsPage.vue'
import ImportPreviewPage from './ImportPreviewPage.vue'
import App from '../../App.vue'
import HomePage from '../HomePage.vue'
import { router as applicationRouter } from '../../router'

const summary={row_count:466,error_rows:10,warning_rows:7,diagnostic_counts:{registration_invalid:6},state_counts:{completed:411,in_progress:34,suspended:4,without_execution:17}}
const batch={id:'batch-1',source_name:'ДЕМО.csv',source_kind:'csv',date_system:'1900' as const,source_sha256:'abc',sheet_name:'Лист1',parser_version:'journal-2026-v1',created_at:'2026-10-28T00:00:00Z',actor:{id:'person-1',full_name:'Делопроизводитель'},row_count:466,summary,version:1,apply_available:false as const,source_url:'/api/v1/imports/batch-1/source/'}
const facts={registration_number:'151/4-1-26',historical_number:'',sequence:151,department_code:'4',category_code:'1',year:2026,state:'completed',specialty_code:'18.1',received_on:'2026-02-12',source_end_on:null,completed_on:null,issued_on:null,result_kind:'expert_conclusion',complexity_level:1,questions:2,categorical:2,probable:null,unresolved:0,unresolved_note:'',amount:null,legacy_duration_days:null,authority_type:'',authority_name:'',official:'',contact:'',basis_text:'',case_description:'',inventory:'',executor_raw:'ДЕМО А.А.',unresolved_reason_raw:'',notes:'',delivery:''}
const row={id:'row-1',source_row:4,raw:{B:'151/4-1-26',D:'Завершена',J:'<script>не исполнять</script>'},formulas:{Q:'=1+1'},extra:{},facts,diagnostics:[{code:'completion_date_missing',severity:'warning',columns:['P'],message:'Дата окончания неизвестна'}],normalization_complete:true}
type Transport=ConstructorParameters<typeof ApiClient>[0]
async function open(url='/imports',transport?:Transport,codes=['imports.results.view','imports.preview'],capability=true){
  const pinia=sessionWith(...codes);useSessionStore().user!.supported_modules=capability?['journal_import_preview']:[]
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/imports',component:ImportPreviewsPage},{path:'/imports/:id',component:ImportPreviewPage},{path:'/workspace',component:{template:'<p>Рабочее место</p>'}}]});await router.push(url)
  const client=new ApiClient(transport??(async input=>json(String(input).includes('/rows/')?page([row]):new URL(String(input),'http://localhost').pathname.endsWith('/imports/')?page([batch]):batch)))
  const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}});await flushPromises();return {wrapper,router,pinia,client}
}
async function choose(wrapper:ReturnType<typeof mount>,file=new File(['demo'],'ДЕМО.csv')){
  Object.defineProperty(wrapper.get('input[type="file"]').element,'files',{value:[file],configurable:true});await wrapper.get('input[type="file"]').trigger('change');return file
}
afterEach(()=>vi.restoreAllMocks());enableAutoUnmount(afterEach)

it('posts only a source preview with explicit reason/file/key, never applies business records',async()=>{
  const writes:{path:string;body:FormData;key:string|null}[]=[]
  const {wrapper}=await open('/imports',async(input,init)=>{if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'});if(init?.method==='POST'){writes.push({path:String(input),body:init.body as FormData,key:new Headers(init.headers).get('Idempotency-Key')});return json({event:{id:'event-1'},batch},201)}return json(page([batch]))})
  await wrapper.get('[data-new-import-preview]').trigger('click');const file=await choose(wrapper);await wrapper.get('[name="import_reason"]').setValue('  Проверить первый лист  ');await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises()
  expect(writes).toHaveLength(1);expect(writes[0]!.path).toBe('/api/v1/imports/preview/');expect(writes[0]!.key).toBeTruthy();const uploaded=writes[0]!.body.get('file') as File;expect(uploaded.name).toBe(file.name);expect(uploaded.size).toBe(4);expect(await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsText(uploaded)})).toBe('demo');expect(writes[0]!.body.get('reason')).toBe('Проверить первый лист');expect(wrapper.get('[data-preview-created] a').attributes('href')).toBe('/imports/batch-1');expect(wrapper.find('[data-apply-import]').exists()).toBe(false)
})
it('replays the same source/body/key after response loss without clearing staged input',async()=>{
  const writes:{key:string|null;file:FormDataEntryValue|null;reason:FormDataEntryValue|null}[]=[]
  const {wrapper}=await open('/imports',async(input,init)=>{if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'});if(init?.method==='POST'){const body=init.body as FormData;writes.push({key:new Headers(init.headers).get('Idempotency-Key'),file:body.get('file'),reason:body.get('reason')});if(writes.length===1)throw new TypeError('Ответ потерян после записи');return json({event:{id:'same-event'},batch},201)}return json(page([]))})
  await wrapper.get('[data-new-import-preview]').trigger('click');await choose(wrapper);await wrapper.get('[name="import_reason"]').setValue('Проверка');await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises();expect(wrapper.text()).toContain('Ответ не получен');await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises();expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);expect(writes[0]!.key).toBeTruthy()
})
it('starts a new attempt when a rejected source is deliberately replaced',async()=>{
  const keys:(string|null)[]=[]
  const {wrapper}=await open('/imports',async(input,init)=>{if(String(input).endsWith('/csrf/'))return json({csrf_token:'t'});if(init?.method==='POST'){keys.push(new Headers(init.headers).get('Idempotency-Key'));return json({code:'invalid_source',message:'Неверный источник',field_errors:{}},400)}return json(page([]))})
  await wrapper.get('[data-new-import-preview]').trigger('click');await choose(wrapper);await wrapper.get('[name="import_reason"]').setValue('Проверка');await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises();await choose(wrapper,new File(['new'],'Исправлено.csv'));await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises();expect(keys).toHaveLength(2);expect(keys[1]).not.toBe(keys[0]);expect(wrapper.get('[name="import_reason"]').element).toHaveProperty('value','Проверка')
})
it.each([403,409])('keeps staged source after server %s instead of pretending apply succeeded',async status=>{
  const {wrapper}=await open('/imports',async(input,init)=>String(input).endsWith('/csrf/')?json({csrf_token:'t'}):init?.method==='POST'?json({code:status===403?'permission_denied':'command_conflict',message:'Проверка отказа',field_errors:{}},status):json(page([])))
  await wrapper.get('[data-new-import-preview]').trigger('click');await choose(wrapper);await wrapper.get('[name="import_reason"]').setValue('Проверка отказа');await wrapper.get('[data-import-upload]').trigger('submit');await flushPromises();expect(wrapper.get('[name="import_reason"]').element).toHaveProperty('value','Проверка отказа');expect(wrapper.text()).toContain('ДЕМО.csv');expect(wrapper.find('[data-preview-created]').exists()).toBe(false)
})
it('guards a selected source before leaving and preserves it when leaving is declined',async()=>{
  const {wrapper,router}=await open();await wrapper.get('[data-new-import-preview]').trigger('click');await choose(wrapper);vi.spyOn(window,'confirm').mockReturnValue(false);await router.push('/workspace');expect(router.currentRoute.value.path).toBe('/imports');expect(wrapper.text()).toContain('ДЕМО.csv')
})
it('does not fetch or advertise snapshots without the supported module',async()=>{
  const paths:string[]=[];const {wrapper,pinia,router}=await open('/imports',async input=>{paths.push(String(input));return json(page([]))},['imports.results.view','imports.preview'],false)
  const app=mount(App,{global:{plugins:[pinia,router]}}),home=mount(HomePage,{global:{plugins:[pinia,router]}});await flushPromises();expect(paths).toEqual([]);expect(wrapper.find('[data-new-import-preview]').exists()).toBe(false);expect(app.find('nav a[href="/imports"]').exists()).toBe(false);expect(home.find('a[href="/imports"]').exists()).toBe(false)
})
it('allows a results-only reader to inspect snapshots without an upload action',async()=>{
  const {wrapper}=await open('/imports',undefined,['imports.results.view']);expect(wrapper.find('[data-new-import-preview]').exists()).toBe(false);expect(wrapper.get('[data-open-import-preview]').text()).toContain('ДЕМО.csv')
})
it('keeps journal pagination in its return URL',async()=>{
  const paths:string[]=[];const {wrapper}=await open('/imports?page=2',async input=>{paths.push(String(input));return json({...page([batch]),count:50,previous:'/imports/?page=1'})});expect(paths).toContain('/api/v1/imports/?page=2');expect(wrapper.get('[data-open-import-preview]').attributes('href')).toContain('return=/imports?page=2')
})
it('opens source reconciliation only with current server support and preserves the source URL',async()=>{
  const {wrapper,pinia}=await open('/imports/batch-1?severity=error',async input=>json(String(input).includes('/rows/')?page([row]):batch),['imports.results.view'])
  expect(wrapper.find('[data-open-reconciliation]').exists()).toBe(false)
  useSessionStore(pinia).user!.supported_modules=['journal_import_preview','journal_application'];await flushPromises()
  const target=new URL(wrapper.get('[data-open-reconciliation]').attributes('href')!,'http://localhost')
  expect(target.pathname).toBe('/imports/batch-1/reconciliation')
  expect(target.searchParams.get('return')).toBe('/imports/batch-1?severity=error')
})
it.each(['/imports','/imports/batch-1'])('does not claim a source was never applied when reopening %s',async url=>{
  const {wrapper}=await open(url,async input=>json(String(input).includes('/rows/')?page([row]):String(input).endsWith('/imports/?page=1')?page([batch]):batch),['imports.results.view'])
  expect(wrapper.text()).not.toContain('рабочие записи ещё не созданы')
  expect(wrapper.text()).toContain('Предпросмотр не меняет рабочие записи')
})
it('shows global snapshot totals while filtering rows before their page and retains unknown values',async()=>{
  const paths:string[]=[];const {wrapper}=await open('/imports/batch-1?severity=warning&state=completed&search=151&page=2',async input=>{paths.push(String(input));return json(String(input).includes('/rows/')?{...page([row]),count:25,previous:'/rows/?page=1'}:batch)})
  expect(paths).toContain('/api/v1/imports/batch-1/rows/?search=151&severity=warning&state=completed&page=2');expect(wrapper.get('[data-import-summary]').text()).toContain('466');await wrapper.get('[data-open-import-row]').trigger('click');expect(wrapper.get('[data-import-row-details]').text()).toContain('Дата окончания неизвестна');expect(wrapper.get('[data-import-row-details]').text()).toContain('<script>не исполнять</script>');expect(wrapper.find('[data-import-row-details] script').exists()).toBe(false);expect(wrapper.get('[data-import-row-details]').text()).toContain('Не указано')
})
it('sends changed row filters with page reset instead of filtering only visible rows',async()=>{
  const paths:string[]=[];const {wrapper}=await open('/imports/batch-1?page=3',async input=>{paths.push(String(input));return json(String(input).includes('/rows/')?page([row]):batch)});await wrapper.get('[name="severity"]').setValue('error');await wrapper.get('[data-import-row-filters]').trigger('submit');await flushPromises();expect(paths.at(-1)).toBe('/api/v1/imports/batch-1/rows/?severity=error&page=1')
})
it('discards an old snapshot row response after switching to another source',async()=>{
  let release!:(value:Response)=>void
  const {wrapper,router}=await open('/imports/batch-1',async input=>{const path=String(input);if(path.includes('/batch-1/rows/'))return new Promise<Response>(resolve=>{release=resolve});return json(path.includes('/rows/')?page([]):path.includes('batch-2')?{...batch,id:'batch-2',source_name:'НОВЫЙ.csv'}:batch)})
  await router.push('/imports/batch-2');await flushPromises();release(json(page([{...row,facts:{...facts,registration_number:'СТАРАЯ-СТРОКА'}}])));await flushPromises();expect(wrapper.text()).toContain('НОВЫЙ.csv');expect(wrapper.text()).not.toContain('СТАРАЯ-СТРОКА')
})
it('never follows an external source URL or an external return target',async()=>{
  const {wrapper}=await open('/imports/batch-1?return=https://other.invalid',async input=>json(String(input).includes('/rows/')?page([]):{...batch,source_url:'https://other.invalid/source'}));expect(wrapper.find('a[download]').exists()).toBe(false);expect(wrapper.get('[data-back-to-imports]').attributes('href')).toBe('/imports')
})

it('advertises the enabled results workplace in navigation and the home page',async()=>{
  const {pinia,router,client}=await open()
  const app=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}}),home=mount(HomePage,{global:{plugins:[pinia,router]}})
  expect(app.find('nav a[href="/imports"]').exists()).toBe(true);expect(home.find('a[href="/imports"]').exists()).toBe(true)
})
it('requires both the module and results permission on real import routes',async()=>{
  sessionWith('imports.results.view');await applicationRouter.push('/imports');expect(applicationRouter.currentRoute.value.path).toBe('/workspace')
  useSessionStore().user!.supported_modules=['journal_import_preview'];await applicationRouter.push('/imports');expect(applicationRouter.currentRoute.value.path).toBe('/imports')
  sessionWith('imports.preview');useSessionStore().user!.supported_modules=['journal_import_preview'];await applicationRouter.push('/imports/batch-1');expect(applicationRouter.currentRoute.value.path).toBe('/workspace')
})
it('does not show old rows under a rejected new filter and can retry that row request',async()=>{
  let failed=false,retried=false
  const {wrapper}=await open('/imports/batch-1',async input=>{if(!String(input).includes('/rows/'))return json(batch);if(failed&&!retried)return json({code:'validation_error',message:'Условия требуют проверки',field_errors:{}},400);return json(page(failed?[]:[row]))})
  expect(wrapper.text()).toContain('151/4-1-26');failed=true;await wrapper.get('[name="severity"]').setValue('error');await wrapper.get('[data-import-row-filters]').trigger('submit');await flushPromises();expect(wrapper.text()).toContain('Условия требуют проверки');expect(wrapper.find('[data-open-import-row]').exists()).toBe(false)
  retried=true;await wrapper.get('[data-retry-import-rows]').trigger('click');await flushPromises();expect(wrapper.text()).toContain('Строк по выбранным условиям нет')
})
