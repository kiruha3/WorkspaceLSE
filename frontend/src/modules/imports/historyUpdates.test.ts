import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter,RouterView } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import type { ReconciliationRow } from '../../api/imports'
import { json,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
import ReconciliationPage from './ReconciliationPage.vue'

enableAutoUnmount(afterEach)
afterEach(()=>vi.restoreAllMocks())
const ref4={id:'d4',code:'4',name:'Отдел4',is_active:true},spec={id:'s1',code:'1.1',name:'Почерк',is_active:true}
const previous={id:'old-choice',row_id:'old-row',version:1,department_id:'d4',specialty_id:'old-spec',employee_ids:['person'],appointment_nature:null,is_commission:null,complex_known:false,complex_group_key:null,statistics_confirmed:false,reason:'Прежний выбор'}
const chosen={...previous,id:'new-choice',row_id:'new-row',version:3,specialty_id:'s1'}
const item:ReconciliationRow={row:{id:'new-row',source_row:4,raw:{B:'151/4-1-26'},facts:{registration_number:'151/4-1-26',department_code:'4',specialty_code:'1.1',executor_raw:'Эксперт А.А.'},formulas:{},extra:{},diagnostics:[],normalization_complete:true},classification:'changed',existing_work:{id:'work',registration_number:'151/4-1-26',version:2},blockers:[],suggested_department:ref4,suggested_specialty:spec,selection:chosen,update_preview:{eligible:true,blockers:[],changes:[{field:'complexity_level',before:1,after:2}],expected_work_version:2,expected_source_row_id:'old-row',previous_selection:previous}}
const options={departments:[ref4],specialties:[spec],employees:[{id:'person',full_name:'Эксперт А.А.',is_active:true}]}
const protocol={id:'update-1',batch_id:'b1',created_at:'2026-10-28T00:00:00Z',created_count:0,existing_count:0,updated_count:1,items:[{row_id:'new-row',expertise_id:'work',action:'updated'}]}
const listing=(current:typeof item)=>({count:1,next:null,previous:null,results:[current],summary:{new:0,changed:1,unchanged:0,invalid:0},batch_id:'b1'})
async function open(transport:typeof fetch,current:typeof item=item,codes=['imports.results.view','imports.reconcile','imports.apply']){
 const pinia=sessionWith(...codes);useSessionStore(pinia).user!.supported_modules=['journal_import_preview','journal_application']
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/imports/:id/reconciliation',component:ReconciliationPage},{path:'/imports/:id',component:{template:'<p>Источник</p>'}},{path:'/expertises/:id',component:{template:'<p>Работа</p>'}}]})
 await router.push('/imports/b1/reconciliation')
 const client=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'t'}):String(input).includes('options')?json(options):init?.method&&init.method!=='GET'?transport(input,init):json(listing(current)))
 const wrapper=mount(RouterView,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:client}}});await flushPromises()
 return {wrapper,router}
}

it('shows typed changes and offers the old people as an unsaved mapping draft with the new specialty',async()=>{
 const current={...item,selection:null} as unknown as typeof item
 const {wrapper}=await open(async()=>json({}),current)
 expect(wrapper.text()).toContain('Обновление исторических записей')
 expect(wrapper.text()).toContain('Категория сложности')
 expect(wrapper.get('[data-update-row]').attributes('disabled')).toBeDefined()
 await wrapper.get('[data-edit-selection]').trigger('click');await flushPromises()
 expect(wrapper.get('[name="selection_specialty"]').element).toHaveProperty('value','s1')
 expect(wrapper.get('input[value="person"]').element).toHaveProperty('checked',true)
 expect(wrapper.text()).toContain('Сохранить сопоставление')
})

it('posts only the explicitly selected update and retries a lost response with identical key and versions',async()=>{
 const writes:{path:string;body:unknown;key:string|null}[]=[]
 const {wrapper}=await open(async(input,init)=>{
  writes.push({path:String(input),body:JSON.parse(String(init?.body)),key:new Headers(init?.headers).get('Idempotency-Key')})
  if(writes.length===1)throw new TypeError('Связь потеряна')
  return json({event:{id:'audit'},application:protocol},201)
 })
 await wrapper.get('[data-update-row]').setValue(true)
 await wrapper.get('[name="update_reason"]').setValue('Исправления проверены')
 await wrapper.get('[data-update-form]').trigger('submit');await flushPromises()
 expect(wrapper.text()).toContain('Повторить ту же попытку')
 expect(wrapper.get('[name="update_reason"]').attributes('disabled')).toBeDefined()
 expect(wrapper.get('[data-update-row]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="update_reason"]').setValue('Исправления проверены ')
 await wrapper.get('[data-update-row]').setValue(false)
 await wrapper.get('[data-update-form]').trigger('submit');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0])
 expect(writes[0]?.path).toBe('/api/v1/imports/b1/updates/')
 expect(writes[0]?.body).toEqual({reason:'Исправления проверены',updates:[{row_id:'new-row',expected_selection_version:3,expected_work_version:2,expected_source_row_id:'old-row'}]})
 expect(writes[0]?.key).toBeTruthy()
 expect(wrapper.text()).toContain('Обновлено: 1')
 expect(wrapper.find('[data-apply-import]').exists()).toBe(false)
})

it('shows a conflict explanation but blocks updating a manually changed work',async()=>{
 const current={...item,update_preview:{...item.update_preview!,eligible:false,blockers:['Есть ручная правка']}}
 const {wrapper}=await open(async()=>json({}),current)
 expect(wrapper.text()).toContain('Есть ручная правка')
 expect(wrapper.get('[data-update-row]').attributes('disabled')).toBeDefined()
})

it('does not expose update controls to a source-only reader',async()=>{
 const readable={...item,update_preview:{...item.update_preview!,changes:[
  {field:'specialty_id',before:'old-uuid',after:'new-uuid',before_label:'3.1 · Документы',after_label:'1.1 · Почерк'},
  {field:'employee_ids',before:['old-person'],after:['new-person'],before_label:'Эксперт А.А.',after_label:'Эксперт Б.Б.'}
 ]}}
 const {wrapper}=await open(async()=>json({}),readable,['imports.results.view'])
 expect(wrapper.text()).toContain('3.1 · Документы');expect(wrapper.text()).toContain('1.1 · Почерк')
 expect(wrapper.text()).toContain('Эксперт Б.Б.');expect(wrapper.text()).not.toContain('old-uuid')
 expect(wrapper.find('[data-update-row]').exists()).toBe(false)
})

it('ignores the previous packet response after changing batch',async()=>{
 let finish!:(r:Response)=>void
 const {wrapper,router}=await open(async()=>new Promise<Response>(r=>{finish=r}))
 await wrapper.get('[data-update-row]').setValue(true);await wrapper.get('[name="update_reason"]').setValue('Проверено')
 await wrapper.get('[data-update-form]').trigger('submit');await flushPromises()
 vi.spyOn(window,'confirm').mockReturnValue(true)
 await router.push('/imports/b2/reconciliation');await flushPromises();finish(json({event:{id:'a'},application:protocol},201));await flushPromises()
 expect(wrapper.text()).not.toContain('Протокол update-1')
 expect(wrapper.find('[name="update_reason"]').exists()).toBe(false)
})
