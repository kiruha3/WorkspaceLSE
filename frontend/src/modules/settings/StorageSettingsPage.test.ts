import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import {createMemoryHistory,createRouter,RouterView} from 'vue-router'
import {ApiClient,apiKey} from '../../api/client'
import {json,sessionWith} from '../../test/fixtures'
import {useSessionStore} from '../../stores/session'
import StorageSettingsPage from './StorageSettingsPage.vue'
import SettingsPage from './SettingsPage.vue'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.restoreAllMocks();sessionStorage.clear()})
const initial={year:2026,path:'',version:0,read_only:true}
const configured={...initial,path:'\\\\server\\share\\2026',version:1,event:{id:'event-one'}}
async function open(transport:typeof fetch=async()=>json(initial),codes=['documents.storage.manage']){
 const pinia=sessionWith(...codes),session=useSessionStore(pinia)
 session.user!.supported_modules=['document_storage_settings','journal_source_settings']
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/settings/storage',component:StorageSettingsPage},{path:'/settings',component:SettingsPage},{path:'/roles',component:{template:'<p>Роли</p>'}},{path:'/imports/source-settings',component:{template:'<p>Источник</p>'}}]})
 await router.push('/settings/storage?year=2026')
 const api=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'t'}):transport(input,init))
 const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}})
 await flushPromises()
 return {wrapper,router,session}
}

it('makes no storage request without the specific permission',async()=>{
 const reads:string[]=[]
 const {wrapper}=await open(async input=>{reads.push(String(input));return json(initial)},['access.roles.manage'])
 expect(reads).toEqual([])
 expect(wrapper.find('[data-storage-form]').exists()).toBe(false)
})

it('saves the root without checking the folder or starting an import',async()=>{
 const calls:{url:string;method:string;body:unknown}[]=[]
 const {wrapper}=await open(async(input,init)=>{
  calls.push({url:String(input),method:init?.method??'GET',body:init?.body?JSON.parse(String(init.body)):null})
  return json(init?.method==='PUT'?configured:initial)
 })
 await wrapper.get('[name="storage_path"]').setValue(configured.path)
 await wrapper.get('[data-storage-form]').trigger('submit');await flushPromises()
 expect(calls).toEqual([{url:'/api/v1/document-storage/2026/',method:'GET',body:null},{url:'/api/v1/document-storage/2026/',method:'PUT',body:{path:configured.path,expected_version:0}}])
 expect(wrapper.text()).toContain('Настройка сохранена')
 expect(wrapper.text()).not.toContain('Папка доступна')
})

it('checks explicitly and clears the old result when path changes',async()=>{
 const writes:unknown[]=[]
 const {wrapper}=await open(async(_input,init)=>{if(init?.method==='POST'){writes.push(JSON.parse(String(init.body)));return json({status:'available',read_only:true})}return json(configured)})
 await wrapper.get('[data-check-storage]').trigger('click');await flushPromises()
 expect(writes).toEqual([{path:configured.path}]);expect(wrapper.text()).toContain('Папка доступна')
 await wrapper.get('[name="storage_path"]').setValue('C:\\other')
 expect(wrapper.find('[data-storage-check-result]').exists()).toBe(false)
})

it('retries an uncertain save with the original key and exact body',async()=>{
 const writes:{body:string;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{
  if(init?.method==='PUT'){writes.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')});if(writes.length===1)throw new TypeError('Lost reply');return json(configured)}
  return json(initial)
 })
 await wrapper.get('[name="storage_path"]').setValue(configured.path)
 await wrapper.get('[data-storage-form]').trigger('submit');await flushPromises()
 expect(wrapper.get('[name="storage_path"]').attributes('disabled')).toBeDefined()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 await wrapper.get('[data-storage-form]').trigger('submit');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);expect(writes[0]!.key).toBeTruthy()
})

it('retains the entered path on a version conflict without silent reload',async()=>{
 const reads:string[]=[]
 const {wrapper}=await open(async(input,init)=>{if(init?.method==='PUT')return json({code:'version_conflict',message:'Настройка уже изменена'},409);reads.push(String(input));return json(initial)})
 await wrapper.get('[name="storage_path"]').setValue(configured.path)
 await wrapper.get('[data-storage-form]').trigger('submit');await flushPromises()
 expect(wrapper.get('[name="storage_path"]').element).toHaveProperty('value',configured.path)
 expect(reads).toHaveLength(1);expect(wrapper.text()).toContain('Настройка уже изменена')
})

it('revocation clears sensitive paths and prevents a prepared submit',async()=>{
 const writes:unknown[]=[]
 const {wrapper,session}=await open(async(_input,init)=>{if(init?.method!=='GET')writes.push(init?.body);return json(configured)})
 const form=wrapper.get('[data-storage-form]')
 session.user!.access={}
 await form.trigger('submit');await flushPromises()
 expect(writes).toEqual([]);expect(wrapper.find('[data-storage-form]').exists()).toBe(false)
 expect(wrapper.text()).not.toContain(configured.path)
})

it('selects another year explicitly without overwriting the first year',async()=>{
 const reads:string[]=[]
 const {wrapper}=await open(async input=>{reads.push(String(input));return json(String(input).includes('2027')?{...initial,year:2027}:initial)})
 await wrapper.get('[name="storage_year"]').setValue('2027')
 await wrapper.get('[data-load-storage-year]').trigger('click');await flushPromises()
 expect(reads).toEqual(['/api/v1/document-storage/2026/','/api/v1/document-storage/2027/'])
 expect(wrapper.get('[name="storage_path"]').element).toHaveProperty('value','')
})

it('shows a settings hub with only available management links',async()=>{
 const {wrapper,router}=await open(async()=>json(initial),['documents.storage.manage','imports.source.manage','access.roles.manage'])
 await router.push('/settings');await flushPromises()
 expect(wrapper.get('[data-setting="storage"]').attributes('href')).toBe('/settings/storage')
 expect(wrapper.get('[data-setting="source"]').attributes('href')).toBe('/imports/source-settings')
 expect(wrapper.get('[data-setting="roles"]').attributes('href')).toBe('/roles')
 expect(wrapper.find('[data-setting="references"]').exists()).toBe(false)
})

it('clears an already displayed path when the server reports role revocation',async()=>{
 const {wrapper,session}=await open(async(_input,init)=>init?.method==='POST'?json({code:'permission_denied',message:'Нет права'},403):json(configured))
 vi.spyOn(session,'refresh').mockResolvedValue()
 await wrapper.get('[data-check-storage]').trigger('click');await flushPromises()
 expect(wrapper.find('[data-storage-form]').exists()).toBe(false)
 expect(wrapper.text()).not.toContain(configured.path)
})
