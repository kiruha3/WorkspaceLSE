import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter,RouterView } from 'vue-router'
import { router as appRouter } from '../../router'
import { ApiClient,apiKey } from '../../api/client'
import { json,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'

enableAutoUnmount(afterEach)
afterEach(()=>vi.restoreAllMocks())
const changed={row_id:'row-1',source_row:473,number:'470/3-2-26',classification:'changed',action:'update',expected_work_version:2,expected_source_row_id:'old-row',expected_selection_version:0,proposal_hash:'a'.repeat(64),work_id:'work-1',eligible:true,blockers:[],selection:{},diagnostics:[],changes:[
 {field:'specialty_id',before:null,after:'spec-16',before_label:'Не заполнено',after_label:'16.1 · Строительная экспертиза',conflict:false},
 {field:'complexity_level',before:3,after:2,conflict:true}
]}
const newRow={...changed,row_id:'row-2',number:'479/4-1-26',classification:'new',action:'create',expected_work_version:null,expected_source_row_id:null,proposal_hash:'b'.repeat(64),work_id:null,changes:[{field:'received_on',before:null,after:'2026-10-29',conflict:false}]}
const listing={batch_id:'b1',summary:{new:1,changed:1,unchanged:476,invalid:0},results:[changed,newRow]}
const protocol={event:{id:'event-1'},batch_id:'b1',created_count:0,updated_count:1,applications:[{id:'app-1',created_count:0,updated_count:1,existing_count:0,created_at:'2026-10-29T03:00:00Z',batch_id:'b1',items:[{row_id:'row-1',expertise_id:'work-1',action:'updated'}]}]}
async function open(transport:typeof fetch,data:unknown=listing,codes=['imports.results.view','imports.reconcile','imports.apply']){
 const pinia=sessionWith(...codes);useSessionStore(pinia).user!.supported_modules=['journal_import_preview','journal_application']
 const route=appRouter.options.routes.find(route=>route.path==='/imports/:id/review')
 const router=createRouter({history:createMemoryHistory(),routes:[route??{path:'/imports/:id/review',component:{template:'<p>Перечень пока не реализован</p>'}},{path:'/expertises',component:{template:'<p>Реестр</p>'}},{path:'/expertises/:id',component:{template:'<p>Карточка</p>'}},{path:'/imports/:id/reconciliation',component:{template:'<p>Сверка</p>'}}]})
 await router.push('/imports/b1/review?return=%2Fexpertises%3Fstate%3Din_progress%26page%3D2')
 const api=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'token'}):init?.method==='POST'?transport(input,init):json(data))
 const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}});await flushPromises()
 return {wrapper,router}
}

it('shows field differences without selecting or writing anything and returns to the filtered registry',async()=>{
 const writes:unknown[]=[]
 const {wrapper}=await open(async(input)=>{writes.push(input);return json(protocol,201)})
 expect(wrapper.text()).toContain('470/3-2-26')
 expect(wrapper.text()).toContain('16.1 · Строительная экспертиза')
 expect(wrapper.text()).toContain('Ручное расхождение')
 expect(wrapper.findAll('input[type="checkbox"]').every(input=>!(input.element as HTMLInputElement).checked)).toBe(true)
 expect(wrapper.get('[data-apply-review]').attributes('disabled')).toBeDefined()
 expect(wrapper.get('[data-back-to-registry]').attributes('href')).toBe('/expertises?state=in_progress&page=2')
 expect(writes).toEqual([])
})

it('sends only the explicitly accepted field, not other changes or another new expertise',async()=>{
 const writes:{body:unknown;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{writes.push({body:JSON.parse(String(init?.body)),key:new Headers(init?.headers).get('Idempotency-Key')});return json(protocol,201)})
 await wrapper.get('[data-review-field="row-1:specialty_id"]').setValue(true)
 await wrapper.get('[data-apply-review]').trigger('click');await flushPromises()
 expect(writes).toHaveLength(1)
 expect(writes[0]!.body).toEqual({selections:[{row_id:'row-1',action:'update',expected_work_version:2,expected_source_row_id:'old-row',expected_selection_version:0,proposal_hash:'a'.repeat(64),accepted_fields:['specialty_id']}]})
 expect(wrapper.text()).toContain('Обновлено: 1')
 expect(wrapper.text()).toContain('Сохранённые в БД изменения')
})

it('bulk selection excludes manual conflicts while a conflict can be accepted explicitly',async()=>{
 const {wrapper}=await open(async()=>json(protocol,201))
 await wrapper.get('[data-select-safe-review]').trigger('click')
 expect(wrapper.get('[data-review-field="row-1:specialty_id"]').element).toHaveProperty('checked',true)
 expect(wrapper.get('[data-review-field="row-1:complexity_level"]').element).toHaveProperty('checked',false)
 expect(wrapper.get('[data-review-create="row-2"]').element).toHaveProperty('checked',true)
 await wrapper.get('[data-review-field="row-1:complexity_level"]').setValue(true)
 expect(wrapper.get('[data-review-field="row-1:complexity_level"]').element).toHaveProperty('checked',true)
})

it('freezes the exact packet and key after a lost response',async()=>{
 const writes:{body:unknown;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{writes.push({body:JSON.parse(String(init?.body)),key:new Headers(init?.headers).get('Idempotency-Key')});if(writes.length===1)throw new TypeError('Lost response');return json(protocol,201)})
 await wrapper.get('[data-review-field="row-1:complexity_level"]').setValue(true)
 await wrapper.get('[data-apply-review]').trigger('click');await flushPromises()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 expect(wrapper.get('[data-review-field="row-1:complexity_level"]').attributes('disabled')).toBeDefined()
 await wrapper.get('[data-review-field="row-1:specialty_id"]').setValue(true)
 await wrapper.get('[data-apply-review]').trigger('click');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0]);expect(writes[0]!.key).toBeTruthy()
})

it('shows blocked records and read-only differences without granting acceptance controls',async()=>{
 const blocked={...changed,eligible:false,blockers:['Работа продолжена в новом учёте.']}
 const {wrapper}=await open(async()=>json(protocol,201),{...listing,results:[blocked]},['imports.results.view'])
 expect(wrapper.text()).toContain('Работа продолжена в новом учёте.')
 expect(wrapper.find('[data-review-field]').exists()).toBe(false)
 expect(wrapper.find('[data-apply-review]').exists()).toBe(false)
})

it('shows no-op source refresh as no changes',async()=>{
 const {wrapper}=await open(async()=>json(protocol,201),{...listing,summary:{new:0,changed:0,unchanged:478,invalid:0},results:[]})
 expect(wrapper.text()).toContain('Изменений нет')
 expect(wrapper.find('[data-apply-review]').exists()).toBe(false)
})

it('does not display an old application result after switching source',async()=>{
 let finish!:(value:Response)=>void
 const {wrapper,router}=await open(async()=>new Promise<Response>(resolve=>{finish=resolve}))
 await wrapper.get('[data-review-field="row-1:specialty_id"]').setValue(true)
 await wrapper.get('[data-apply-review]').trigger('click');await flushPromises()
 vi.spyOn(window,'confirm').mockReturnValue(true)
 await router.push('/imports/b2/review');await flushPromises()
 finish(json(protocol,201));await flushPromises()
 expect(wrapper.text()).not.toContain('Обновлено: 1')
})
