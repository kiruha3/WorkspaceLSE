import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { ApiClient,apiKey } from '../../api/client'
import type { Expertise } from '../../api/types'
import { json,page,sessionWith } from '../../test/fixtures'
import { basis,expertise,testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'

enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const previous={id:'prior-1',reference:'№ 12 от 2025 г.',organization_name:'Предыдущее учреждение',organization_group:null,same_input_data:null,confirms_previous:null,document_id:null,document:null}
const classification={id:null,can_edit:true,edit_permission:'expertise.work.update',appointment_nature:null,previous_complete:false,previous_conclusions:[],revisions:[]}
const initial={...expertise,origin_kind:'historical',appointment_nature:null,allowed_actions:[],classification} as unknown as Expertise
type Write={path:string;body:any;key:string|null}
async function open(current=initial,respond?:(write:Write,n:number)=>Response|Promise<Response>){
 let work=current;const writes:Write[]=[],router=await testRouter('/expertises/work-1')
 const wrapper=mount(ExpertisePage,{global:{plugins:[sessionWith('expertise.view','expertise.work.update','documents.upload','documents.view'),router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
  const path=String(input);if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
  if(init?.method==='POST'){const write={path,body:init.body instanceof FormData?init.body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(write);return respond?respond(write,writes.length):json({event:{id:'revision'},expertise:{...work,version:2}})}
  if(path.endsWith('/classification/'))return json({organization_groups:[{code:'ministry',name:'ФБУ СЭУ Минюста России'},{code:'other_state',name:'Иные государственные СЭУ'},{code:'other',name:'Иные организации и частные эксперты'}]})
  if(path.includes('/documents/?'))return json(page([{...basis,id:'existing-document',kind:'expert_conclusion'}]))
  return json(work)
 })}}});await flushPromises()
 return {wrapper,writes,router,set:(next:Expertise)=>{work=next},refresh:async()=>{await wrapper.findAll('button').find(b=>b.text()==='Обновить серверные сведения')!.trigger('click');await flushPromises()}}
}
async function edit(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){await wrapper.get('[data-classification-edit]').trigger('click');await flushPromises();await wrapper.get('[name="classification_reason"]').setValue('Сверено с постановлением');await flushPromises()}
async function add(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){await wrapper.get('[data-add-previous]').trigger('click');await wrapper.get('[name="previous_reference"]').setValue('№ 12 от 2025 г.');await flushPromises()}
it('does not invent primary nature and obeys server readonly even with a client grant',async()=>{
 const {wrapper}=await open({...initial,classification:{...classification,can_edit:false}} as unknown as Expertise)
 expect(wrapper.get('[data-classification-panel]').text()).toContain('Не уточнён');expect(wrapper.find('[data-classification-edit]').exists()).toBe(false)
})
it('saves full unknown/false facts without changing composition, number or department',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[name="classification_nature"]').setValue('repeated');await add(wrapper)
 await wrapper.get('[name="previous_same_input_data"]').setValue('false');await wrapper.get('[name="previous_confirms"]').setValue('true')
 await wrapper.get('[data-classification-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.path).toBe('/api/v1/expertises/work-1/classification/');expect(writes[0]!.key).toBeTruthy()
 expect(writes[0]!.body).toEqual({expected_version:1,reason:'Сверено с постановлением',appointment_nature:'repeated',previous_complete:false,previous_conclusions:[{reference:'№ 12 от 2025 г.',organization_name:'',organization_group:null,same_input_data:false,confirms_previous:true,document_id:null}]})
})
it('requires a previous entry before declaring the repeated list complete and supports removal',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[name="classification_nature"]').setValue('repeated');await wrapper.get('[name="previous_complete"]').setValue(true)
 expect(wrapper.get('[data-classification-submit]').attributes('disabled')).toBeDefined();await add(wrapper)
 expect(wrapper.get('[data-classification-submit]').attributes('disabled')).toBeUndefined();await wrapper.get('[data-remove-previous]').trigger('click')
 await wrapper.get('[data-classification-form]').trigger('submit');await flushPromises();expect(writes).toHaveLength(0)
})
it('native nature cannot be cleared while historical unknown can be explicit',async()=>{
 const {wrapper}=await open({...initial,origin_kind:'native',appointment_nature:'primary',classification:{...classification,appointment_nature:'primary'}} as unknown as Expertise);await edit(wrapper)
 expect(wrapper.get('[name="classification_nature"]').findAll('option').map(o=>o.attributes('value'))).not.toContain('')
})
it('keeps exact previous document references and renders document-only history changes readably',async()=>{
 const before={...previous,document_id:'old-document'},after={...previous,document_id:'new-document'}
 const work={...initial,appointment_nature:'repeated',classification:{...classification,appointment_nature:'repeated',previous_conclusions:[previous],revisions:[{id:'r1',number:1,actor:{id:'a',full_name:'Эксперт'},created_at:'2026-10-28T01:00:00Z',reason:'Заменена ссылка',before:{previous_conclusions:[before]},after:{previous_conclusions:[after]}}]}} as unknown as Expertise
 const {wrapper,writes}=await open(work);const history=wrapper.get('[data-classification-panel] .subsection')
 expect(history.text()).toContain('old-document');expect(history.text()).toContain('new-document');expect(history.text()).not.toContain('"organization_name"')
 await edit(wrapper);await wrapper.get('[name="previous_document_id"]').setValue('existing-document');await wrapper.get('[data-classification-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.body.previous_conclusions[0].document_id).toBe('existing-document')
})
it('uploads a previous conclusion once and freezes the complete request after a lost reply',async()=>{
 let calls=0
 const {wrapper,writes}=await open(initial,async w=>{if(w.path==='/api/v1/documents/')return json({...basis,id:'new-document',kind:'expert_conclusion',source_kind:'uploaded_copy',versions:[]});if(w.path.endsWith('/versions/'))return json({id:'file-v1',number:1,file_name:'prior.txt',size:5,content_type:'text/plain',uploaded_at:'2026-10-28T01:00:00Z'});calls++;if(calls===1)throw new TypeError('Lost');return json({event:{id:'same'},expertise:{...initial,version:2}})})
 await edit(wrapper);await wrapper.get('[name="classification_nature"]').setValue('repeated');await add(wrapper);await wrapper.get('[data-document-new]').trigger('click')
 await wrapper.get('[name="document_title"]').setValue('Прежнее заключение');await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
 const input=wrapper.get('[name="basis_file"]');Object.defineProperty(input.element,'files',{value:[new File(['prior'],'prior.txt',{type:'text/plain'})]});await input.trigger('change')
 await wrapper.get('[data-classification-form]').trigger('submit');await flushPromises();expect(wrapper.get('[data-classification-fields]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="previous_reference"]').setValue('Поздний ввод');await wrapper.get('[data-classification-form]').trigger('submit');await flushPromises()
 expect(writes.filter(w=>w.path==='/api/v1/documents/')).toHaveLength(1);expect(writes.filter(w=>w.path.endsWith('/versions/'))).toHaveLength(1)
 expect(writes[2]!.body.previous_conclusions[0].document_id).toBe('new-document');expect(writes[3]).toEqual(writes[2]);expect(writes[2]!.body.previous_conclusions[0].reference).toBe('№ 12 от 2025 г.')
})
it('retains the draft through loss and 409, then explicitly takes the refreshed version',async()=>{
 const state=await open(initial,async(_,n)=>{if(n===1)throw new TypeError('Lost');return n===2?json({code:'version_conflict',message:'Изменилась версия'},409):json({event:{id:'saved'},expertise:{...initial,version:3}})})
 await edit(state.wrapper);await add(state.wrapper);await state.wrapper.get('[data-classification-form]').trigger('submit');await flushPromises();await state.wrapper.get('[data-classification-form]').trigger('submit');await flushPromises()
 expect(state.writes[1]).toEqual(state.writes[0]);state.set({...initial,version:2});await state.refresh();expect((state.wrapper.get('[name="previous_reference"]').element as HTMLInputElement).value).toBe('№ 12 от 2025 г.')
 await state.wrapper.get('[data-classification-accept-version]').trigger('click');await state.wrapper.get('[data-classification-form]').trigger('submit');await flushPromises()
 expect(state.writes[2]!.body.expected_version).toBe(2);expect(state.writes[2]!.key).not.toBe(state.writes[0]!.key)
})
it('preserves input on a forbidden save and blocks an accidental route leave',async()=>{
 const state=await open(initial,()=>json({message:'Нет прав'},403));await edit(state.wrapper);await add(state.wrapper)
 await state.wrapper.get('[data-classification-form]').trigger('submit');await flushPromises();expect(state.wrapper.text()).toContain('Нет прав')
 vi.spyOn(window,'confirm').mockReturnValue(false);await state.router.push('/expertises');expect(state.router.currentRoute.value.path).toBe('/expertises/work-1');expect(state.wrapper.get('[name="previous_reference"]').element).toHaveProperty('value','№ 12 от 2025 г.')
})
it('ignores a late classification save when the user moved to another card',async()=>{
 let finish!:(response:Response)=>void
 const state=await open(initial,()=>new Promise<Response>(resolve=>{finish=resolve}));await edit(state.wrapper);await add(state.wrapper)
 await state.wrapper.get('[data-classification-form]').trigger('submit');await flushPromises();vi.spyOn(window,'confirm').mockReturnValue(true)
 state.set({...initial,id:'work-2',registration_number:'152/4-1-26'});await state.router.push('/expertises/work-2');await flushPromises();finish(json({event:{id:'late'},expertise:{...initial,version:2}}));await flushPromises()
 expect(state.wrapper.get('h1').text()).toBe('152/4-1-26')
})
