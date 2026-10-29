import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import {createMemoryHistory,createRouter,RouterView} from 'vue-router'
import {router as appRouter} from '../../router'
import {ApiClient,apiKey} from '../../api/client'
import {json,sessionWith} from '../../test/fixtures'
import {useSessionStore} from '../../stores/session'
import GoogleSourceSettingsPage from './GoogleSourceSettingsPage.vue'

enableAutoUnmount(afterEach);afterEach(()=>{vi.restoreAllMocks();sessionStorage.clear()})
const initial={url:'https://docs.google.com/spreadsheets/d/DEMO_old_sheet_123/edit#gid=0',gid:'0',sheet_name:'Лист1',version:0}
const saved={url:'https://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit#gid=17',gid:'17',sheet_name:'Журнал 2026',version:1,event:{id:'saved-event'}}
async function open(transport:typeof fetch=async()=>json(initial),codes=['imports.source.manage'],supported=true){
 const pinia=sessionWith(...codes),session=useSessionStore(pinia)
 session.user!.supported_modules=supported?['journal_source_settings']:[]
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/imports/source-settings',component:GoogleSourceSettingsPage},{path:'/expertises',component:{template:'<p>Реестр</p>'}}]})
 await router.push('/imports/source-settings?return=%2Fexpertises%3Fpage%3D2')
 const api=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'t'}):transport(input,init))
 const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}});await flushPromises()
 return {wrapper,router,session}
}

it('requires the specific role permission and server capability before reading or editing',async()=>{
 const reads:string[]=[]
 const {wrapper}=await open(async input=>{reads.push(String(input));return json(initial)},['imports.preview','imports.results.view'])
 expect(reads).toEqual([]);expect(wrapper.find('[data-source-settings-form]').exists()).toBe(false)
 const unsupported=await open(async input=>{reads.push(String(input));return json(initial)},['imports.source.manage'],false)
 expect(reads).toEqual([]);expect(unsupported.wrapper.find('[data-source-settings-form]').exists()).toBe(false)
})

it('registers settings under its own permission instead of the source-preview permission',()=>{
 const target=appRouter.resolve('/imports/source-settings')
 expect(target.matched[0]?.path).toBe('/imports/source-settings')
 expect(target.meta.permission).toBe('imports.source.manage')
 expect(target.meta.institutionPermissionsAny).toEqual(['imports.source.manage'])
 expect(target.meta.supportedModule).toBe('journal_source_settings')
})

it('captures gid from a pasted URL but saves the explicitly edited gid and current version without importing',async()=>{
 const writes:{path:string;body:unknown;key:string|null}[]=[]
 const {wrapper}=await open(async(input,init)=>{
  if(init?.method==='PUT'){writes.push({path:String(input),body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')});return json(saved)}
  return json(initial)
 })
 expect(wrapper.get('[name="source_url"]').element).toHaveProperty('value',initial.url)
 await wrapper.get('[name="source_url"]').setValue('https://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit#gid=9')
 expect(wrapper.get('[name="source_gid"]').element).toHaveProperty('value','9')
 await wrapper.get('[name="source_gid"]').setValue('17')
 await wrapper.get('[name="source_sheet_name"]').setValue('  Журнал 2026  ')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(writes).toEqual([{path:'/api/v1/imports/google-source/settings/',body:{url:'https://docs.google.com/spreadsheets/d/DEMO_new_sheet_123/edit#gid=9',gid:'17',sheet_name:'Журнал 2026',expected_version:0},key:expect.any(String)}])
 expect(wrapper.text()).toContain('Источник сохранён')
 expect(wrapper.get('[name="source_url"]').element).toHaveProperty('value',saved.url)
 expect(wrapper.get('[data-back-from-source-settings]').attributes('href')).toBe('/expertises?page=2')
})

it('locks the exact settings packet after a lost response and retries without a second key',async()=>{
 const writes:{body:string;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{
  if(init?.method==='PUT'){writes.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});if(writes.length===1)throw new TypeError('Lost reply');return json(saved)}return json(initial)
 })
 await wrapper.get('[name="source_sheet_name"]').setValue('Журнал 2026')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(wrapper.get('[name="source_sheet_name"]').attributes('disabled')).toBeDefined()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);expect(writes[0]!.key).toBeTruthy()
})

it('keeps entered settings after a stale-version error and does not silently fetch a different source',async()=>{
 const reads:string[]=[]
 const {wrapper}=await open(async(input,init)=>{if(init?.method==='PUT')return json({code:'version_conflict',message:'Настройка уже изменена'},409);reads.push(String(input));return json(initial)})
 await wrapper.get('[name="source_sheet_name"]').setValue('Мой журнал')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(wrapper.get('[name="source_sheet_name"]').element).toHaveProperty('value','Мой журнал')
 expect(wrapper.get('[name="source_sheet_name"]').attributes('disabled')).toBeUndefined()
 expect(reads).toEqual(['/api/v1/imports/google-source/settings/'])
 expect(wrapper.text()).toContain('Настройка уже изменена')
})

it('revoking the role prevents submission of an already open form',async()=>{
 const writes:unknown[]=[]
 const {wrapper,session}=await open(async(_input,init)=>{if(init?.method==='PUT')writes.push(init.body);return json(initial)})
 await wrapper.get('[name="source_sheet_name"]').setValue('Мой журнал')
 const form=wrapper.get('[data-source-settings-form]')
 session.user!.access={}
 await form.trigger('submit');await flushPromises()
 expect(writes).toEqual([])
 expect(wrapper.find('[data-source-settings-form]').exists()).toBe(false)
})

it('keeps an edited source form when leaving is declined',async()=>{
 const {wrapper,router}=await open()
 await wrapper.get('[name="source_sheet_name"]').setValue('Мой журнал')
 vi.spyOn(window,'confirm').mockReturnValue(false)
 await router.push('/expertises')
 expect(router.currentRoute.value.path).toBe('/imports/source-settings')
})

it('restores the same unresolved packet after confirmed navigation away and back',async()=>{
 const writes:{body:string;key:string|null}[]=[]
 const {wrapper,router}=await open(async(_input,init)=>{
  if(init?.method==='PUT'){writes.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});if(writes.length===1)throw new TypeError('Committed but reply lost');return json(saved)}return json(initial)
 })
 await wrapper.get('[name="source_sheet_name"]').setValue('Журнал 2026')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 vi.spyOn(window,'confirm').mockReturnValue(true)
 await router.push('/expertises');await flushPromises()
 await router.push('/imports/source-settings');await flushPromises()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 expect(wrapper.get('[name="source_sheet_name"]').element).toHaveProperty('value','Журнал 2026')
 expect(wrapper.get('[name="source_sheet_name"]').attributes('disabled')).toBeDefined()
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0])
})

it.each(['own','departments'])('hides settings and skips reads when a role is limited to %s',async limit=>{
 const reads:string[]=[]
 const {wrapper,session}=await open(async input=>{reads.push(String(input));return json(initial)},[])
 session.user!.access={'imports.source.manage':[{scope:'institution',scope_limit:limit,department_ids:[],role_id:'r1',role_name:'Источник',assignment_id:'a1'}]}
 await flushPromises()
 expect(reads).toEqual([])
 expect(wrapper.find('[data-source-settings-form]').exists()).toBe(false)
})

it('keeps an unresolved packet private to the signed-in user and restores it only for that user',async()=>{
 const writes:{body:string;key:string|null}[]=[]
 const {wrapper,session}=await open(async(_input,init)=>{
  if(init?.method==='PUT'){writes.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});if(writes.length===1)throw new TypeError('Lost reply');return json(saved)}return json(initial)
 })
 await wrapper.get('[name="source_sheet_name"]').setValue('Журнал 2026')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 session.user={...session.user!,id:'user-2'};await flushPromises()
 expect(wrapper.get('[name="source_sheet_name"]').element).toHaveProperty('value','Лист1')
 expect(wrapper.text()).not.toContain('Повторить ту же попытку')
 session.user={...session.user!,id:'user-1'};await flushPromises()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 expect(wrapper.get('[name="source_sheet_name"]').element).toHaveProperty('value','Журнал 2026')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0])
})

it('does not send a save when browser storage cannot retain its replay packet',async()=>{
 const writes:unknown[]=[]
 const {wrapper}=await open(async(_input,init)=>{if(init?.method==='PUT')writes.push(init.body);return json(initial)})
 vi.spyOn(window,'sessionStorage','get').mockImplementation(()=>{throw new Error('Storage unavailable')})
 await wrapper.get('[name="source_sheet_name"]').setValue('Журнал 2026')
 await wrapper.get('[data-source-settings-form]').trigger('submit');await flushPromises()
 expect(writes).toEqual([])
 expect(wrapper.text()).toContain('запрос не отправлен')
 expect(wrapper.get('[name="source_sheet_name"]').attributes('disabled')).toBeUndefined()
})
