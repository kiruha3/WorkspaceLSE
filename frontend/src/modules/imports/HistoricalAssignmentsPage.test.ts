import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import {createMemoryHistory,createRouter,RouterView} from 'vue-router'
import {router as appRouter} from '../../router'
import {ApiClient,apiKey} from '../../api/client'
import {json,sessionWith} from '../../test/fixtures'
import {useSessionStore} from '../../stores/session'

enableAutoUnmount(afterEach)
afterEach(()=>{vi.restoreAllMocks();sessionStorage.clear()})
const path='/settings/historical-assignments'
const row=(id:string,eligible=true)=>({expertise_id:id,number:`${id}/4-1-26`,state:'in_progress',expected_version:1,proposal_hash:`hash-${id}`,history_id:`h-${id}`,source_row_id:`s-${id}`,batch_id:'batch',source_row:4,executor_raw:'Имя из журнала',specialty:'18.1',operational:false,employees:[{id:'expert',full_name:'Иванов Иван'}],eligible,blockers:eligible?[]:['Специальность не подтверждена.']})
const data={results:[row('1'),row('2'),row('3',false)],eligible_count:2}
async function open(transport:typeof fetch=async()=>json(data),codes=['imports.results.view','imports.apply','expertise.view','expertise.assign']){
 const pinia=sessionWith(...codes),session=useSessionStore(pinia)
 session.user!.supported_modules=['journal_import_preview','journal_application','historical_assignment_import']
 const component=appRouter.getRoutes().find(route=>route.path===path)?.components?.default
 expect(component).toBeDefined()
 const router=createRouter({history:createMemoryHistory(),routes:[{path,component:component!},{path:'/settings',component:{template:'<p>Настройки</p>'}},{path:'/expertises/:id',component:{template:'<p>Экспертиза</p>'}},{path:'/imports/:id/reconciliation',component:{template:'<p>Сверка</p>'}}]})
 await router.push(path)
 const api=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'t'}):transport(input,init))
 const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}})
 await flushPromises();return{wrapper,session}
}

it('selects without writing, allows exclusions and applies only selected works',async()=>{
 const writes:{body:any;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{
  if(init?.method==='POST'){writes.push({body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')});return json({applied_count:1,expertise_ids:['2'],event_ids:['event']},201)}
  return json(data)
 })
 vi.spyOn(window,'confirm').mockReturnValue(true)
 await wrapper.get('[data-select-eligible]').trigger('click');expect(writes).toEqual([])
 await wrapper.get('[data-work="1"]').setValue(false)
 await wrapper.get('.transfer-apply input').setValue('')
 await wrapper.get('[data-apply-assignments]').trigger('click');await flushPromises()
 expect(writes).toHaveLength(1)
 expect(writes[0]!.body.selections).toEqual([{expertise_id:'2',expected_version:1,proposal_hash:'hash-2'}])
 expect(writes[0]!.body.reason).toBe('')
 expect(wrapper.text()).toContain('Перенесено экспертиз: 1')
})

it('explains blocked rows and does not send after cancelled confirmation',async()=>{
 const writes=vi.fn()
 const {wrapper}=await open(async(_input,init)=>{if(init?.method==='POST')writes();return json(data)})
 expect(wrapper.get('[data-work="3"]').attributes('disabled')).toBeDefined()
 expect(wrapper.text()).toContain('Специальность не подтверждена.')
 await wrapper.get('[data-select-eligible]').trigger('click')
 vi.spyOn(window,'confirm').mockReturnValue(false)
 await wrapper.get('[data-apply-assignments]').trigger('click');await flushPromises()
 expect(writes).not.toHaveBeenCalled()
})

it('freezes the packet and retry key after a lost response',async()=>{
 const packets:{body:string;key:string|null}[]=[]
 const {wrapper}=await open(async(_input,init)=>{
  if(init?.method==='POST'){
   packets.push({body:String(init.body),key:new Headers(init.headers).get('Idempotency-Key')})
   if(packets.length===1)throw new TypeError('Network lost')
   return json({applied_count:2,expertise_ids:['1','2'],event_ids:['e1','e2']},201)
  }return json(data)
 })
 vi.spyOn(window,'confirm').mockReturnValue(true)
 await wrapper.get('[data-select-eligible]').trigger('click')
 await wrapper.get('[data-apply-assignments]').trigger('click');await flushPromises()
 expect(wrapper.get('[data-work="1"]').attributes('disabled')).toBeDefined()
 await wrapper.get('[data-apply-assignments]').trigger('click');await flushPromises()
 expect(packets).toHaveLength(2);expect(packets[1]).toEqual(packets[0])
})

it('shows the reason when import permission is missing and disallows application',async()=>{
 const {wrapper}=await open(undefined,['imports.results.view','expertise.view','expertise.assign'])
 expect(wrapper.text()).toContain('Применять подтверждённый пакет переноса')
 expect(wrapper.get('[data-apply-assignments]').attributes('disabled')).toBeDefined()
})

it('does not reuse a packet after an account switch and hides data after read permission revocation',async()=>{
 const {wrapper,session}=await open()
 await wrapper.get('[data-select-eligible]').trigger('click')
 session.user!.id='another-user';await flushPromises()
 expect(wrapper.get('[data-work="1"]').element).toHaveProperty('checked',false)
 session.user!.access={};await flushPromises()
 expect(wrapper.find('[data-work="1"]').exists()).toBe(false)
})

it('clears stale selections and reloads the preview when department scope changes',async()=>{
 let reads=0
 const {wrapper,session}=await open(async()=>{reads++;return json(reads===1?data:{results:[],eligible_count:0})})
 await wrapper.get('[data-select-eligible]').trigger('click')
 session.user!.access['expertise.view']![0]!.scope='departments'
 session.user!.access['expertise.view']![0]!.department_ids=['other-department']
 await flushPromises()
 expect(reads).toBe(2);expect(wrapper.find('[data-work="1"]').exists()).toBe(false)
})
