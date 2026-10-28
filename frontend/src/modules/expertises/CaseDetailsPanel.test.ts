import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { ApiClient,apiKey } from '../../api/client'
import type { Expertise } from '../../api/types'
import { json,sessionWith } from '../../test/fixtures'
import { basis,expertise,testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'
enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const authority={id:'sk',code:'sk',name:'Следственные органы СК РФ',is_active:true,version:1,report_group:'sk'}
const details={id:null,source:'history',can_edit:true,edit_permission:'expertise.work.update',authority_type:null,authority_type_raw:'Следственные органы СК РФ',authority_name:'Исходное управление',official:'Следователь',contact:'',case_number:'',case_description:'Описание дела',basis_text:'Постановление',inventory:'Опись',questions_text:'',decree3214:null,decree_document_id:null,decree_document:null,decree_basis:'',revisions:[]}
const initial={...expertise,allowed_actions:[],case_details:details} as unknown as Expertise
type Write={path:string;body:any;key:string|null}
async function open(current=initial,respond?:(write:Write,n:number)=>Response|Promise<Response>){
 let work=current;const writes:Write[]=[],router=await testRouter('/expertises/work-1')
 const wrapper=mount(ExpertisePage,{global:{plugins:[sessionWith('expertise.view','expertise.work.update','documents.upload','documents.view'),router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
  const path=String(input);if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
  if(init?.method==='POST'){const write={path,body:init.body instanceof FormData?init.body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(write);return respond?respond(write,writes.length):json({event:{id:'revision'},expertise:{...work,version:2}})}
  if(path.endsWith('/case-details/'))return json({authority_types:[authority,{...authority,id:'inactive',name:'Ранее использовался',is_active:false},{...authority,id:'forbidden',name:'Новый неактивный',is_active:false}],initial_authority_type_id:current.case_details?.source==='typed'?null:'sk',retained_authority_type_ids:['inactive']})
  if(path.includes('/documents/'))return json(basis)
  return json(work)
 })}}});await flushPromises()
 return {wrapper,writes,router,set:(next:Expertise)=>{work=next},refresh:async()=>{await wrapper.findAll('button').find(b=>b.text()==='Обновить серверные сведения')!.trigger('click');await flushPromises()}}
}
async function edit(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){await wrapper.get('[data-case-edit]').trigger('click');await flushPromises();await wrapper.get('[name="case_reason"]').setValue('Сверено с делом')}
it('shows source facts and offers only the server-authorized action',async()=>{
 const {wrapper}=await open({...initial,case_details:{...details,can_edit:false}} as unknown as Expertise)
 expect(wrapper.get('[data-case-panel]').text()).toContain('Исходное управление');expect(wrapper.find('[data-case-edit]').exists()).toBe(false)
})
it('saves explicit unknown separately from false and preserves registration identity',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper)
 expect(wrapper.get('[name="case_authority_type_id"]').findAll('option').map(o=>o.attributes('value'))).toEqual(['','sk','inactive'])
 await wrapper.get('[name="case_authority_type_id"]').setValue('');await wrapper.get('[name="case_authority_name"]').setValue('')
 await wrapper.get('[name="case_decree3214"]').setValue('false');await wrapper.get('[data-case-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.path).toBe('/api/v1/expertises/work-1/case-details/');expect(writes[0]!.key).toBeTruthy()
 expect(writes[0]!.body).toEqual({expected_version:1,reason:'Сверено с делом',authority_type_id:null,authority_name:'',official:'Следователь',contact:'',case_number:'',case_description:'Описание дела',basis_text:'Постановление',inventory:'Опись',questions_text:'',decree3214:false,decree_document_id:null,decree_basis:''})
})
it('keeps a typed unknown authority unknown instead of restoring source suggestion',async()=>{
 const {wrapper,writes}=await open({...initial,case_details:{...details,id:'profile',source:'typed',authority_type_raw:''}} as unknown as Expertise);await edit(wrapper)
 expect((wrapper.get('[name="case_authority_type_id"]').element as HTMLSelectElement).value).toBe('')
 await wrapper.get('[data-case-form]').trigger('submit');await flushPromises();expect(writes[0]!.body.decree3214).toBeNull()
})
it('requires actual evidence and explanation for 3214, then sends the selected document',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[name="case_decree3214"]').setValue('true')
 expect(wrapper.get('[data-case-submit]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="case_decree_basis"]').setValue('Подтверждено постановлением');await wrapper.get('[name="case_document_id"]').setValue('document-1')
 await wrapper.get('[data-case-form]').trigger('submit');await flushPromises();expect(writes[0]!.body).toMatchObject({decree3214:true,decree_document_id:'document-1',decree_basis:'Подтверждено постановлением'})
})
it('creates a real document once and freezes the case packet after a lost response',async()=>{
 let metadataCalls=0
 const {wrapper,writes}=await open(initial,async w=>{if(w.path==='/api/v1/documents/')return json({...basis,id:'new-document'});metadataCalls++;if(metadataCalls===1)throw new TypeError('Lost');return json({event:{id:'same'},expertise:{...initial,version:2}})})
 await edit(wrapper);await wrapper.get('[name="case_decree3214"]').setValue('true');await wrapper.get('[name="case_decree_basis"]').setValue('Явное основание')
 await wrapper.get('[name="case_document_mode"]').setValue('new');await wrapper.get('[name="document_title"]').setValue('Основание 3214')
 await wrapper.get('[data-case-form]').trigger('submit');await flushPromises();expect(wrapper.get('[data-case-fields]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="case_authority_name"]').setValue('Не должно попасть в повтор')
 await wrapper.get('[data-case-form]').trigger('submit');await flushPromises()
 expect(writes.filter(w=>w.path==='/api/v1/documents/')).toHaveLength(1);expect(writes[2]).toEqual(writes[1]);expect(writes[1]!.body.decree_document_id).toBe('new-document')
})
it('preserves draft through lost response then 409 and explicitly adopts refreshed version',async()=>{
 const state=await open(initial,async(_,n)=>{if(n===1)throw new TypeError('Lost');return n===2?json({code:'version_conflict',message:'Изменилась версия'},409):json({event:{id:'saved'},expertise:{...initial,version:3}})})
 await edit(state.wrapper);await state.wrapper.get('[name="case_case_number"]').setValue('Дело 22')
 await state.wrapper.get('[data-case-form]').trigger('submit');await flushPromises();await state.wrapper.get('[data-case-form]').trigger('submit');await flushPromises()
 expect(state.writes[1]).toEqual(state.writes[0]);state.set({...initial,version:2});await state.refresh()
 expect((state.wrapper.get('[name="case_case_number"]').element as HTMLInputElement).value).toBe('Дело 22')
 await state.wrapper.get('[data-case-accept-version]').trigger('click');await state.wrapper.get('[data-case-form]').trigger('submit');await flushPromises()
 expect(state.writes[2]!.body.expected_version).toBe(2);expect(state.writes[2]!.key).not.toBe(state.writes[0]!.key)
})
it('keeps input on denied save and guards unsaved navigation',async()=>{
 const state=await open(initial,()=>json({message:'Нет прав'},403));await edit(state.wrapper)
 await state.wrapper.get('[data-case-form]').trigger('submit');await flushPromises();expect(state.wrapper.text()).toContain('Нет прав')
 const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);await state.router.push('/expertises');expect(state.router.currentRoute.value.path).toBe('/expertises/work-1');expect(confirm).toHaveBeenCalled()
})
it('ignores a late save for a previous work instead of replacing the new card',async()=>{
 let finish!:(response:Response)=>void
 const state=await open(initial,()=>new Promise<Response>(resolve=>{finish=resolve}));await edit(state.wrapper)
 await state.wrapper.get('[data-case-form]').trigger('submit');await flushPromises();vi.spyOn(window,'confirm').mockReturnValue(true)
 state.set({...initial,id:'work-2',registration_number:'152/4-1-26'});await state.router.push('/expertises/work-2');await flushPromises()
 finish(json({event:{id:'late'},expertise:{...initial,version:2}}));await flushPromises();expect(state.wrapper.get('h1').text()).toBe('152/4-1-26')
})
