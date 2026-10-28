import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { ApiClient,apiKey } from '../../api/client'
import type { Expertise } from '../../api/types'
import { json,sessionWith } from '../../test/fixtures'
import { basis,expertise,testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'
enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const reasonRef={id:'reason-1',code:'expert_workload',name:'Загруженность экспертов',is_active:true,version:1,report_group:'expert_workload'}
const timing={id:null,can_edit:true,edit_permission:'expertise.work.update',reasons_complete:false,primary_reason_id:null,reasons:[],notification_sent:null,notification_on:null,notification_document_id:null,notification_document:null,extension_requested:null,request_on:null,request_document_id:null,request_document:null,deadline_breached:null,breach_basis:'',breach_document_id:null,breach_document:null,revisions:[]}
const initial={...expertise,allowed_actions:[],timing} as unknown as Expertise
type Write={path:string;body:any;key:string|null}
async function open(current=initial,respond?:(write:Write,n:number)=>Response|Promise<Response>){
 let work=current;const writes:Write[]=[],router=await testRouter('/expertises/work-1')
 const wrapper=mount(ExpertisePage,{global:{plugins:[sessionWith('expertise.view','expertise.work.update','documents.upload','documents.view'),router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
  const path=String(input);if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
  if(init?.method==='POST'){const write={path,body:init.body instanceof FormData?init.body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(write);return respond?respond(write,writes.length):json({event:{id:'revision'},expertise:{...work,version:2}})}
  if(path.endsWith('/timing/'))return json({delay_reasons:[reasonRef,{...reasonRef,id:'retained',name:'Ранее использовалась',is_active:false},{...reasonRef,id:'forbidden',name:'Не выбиралась',is_active:false}],retained_reason_ids:['retained'],delay_reason_policy:null})
  return json(work)
 })}}});await flushPromises();return {wrapper,writes,router,set:(next:Expertise)=>{work=next},refresh:async()=>{await wrapper.findAll('button').find(b=>b.text()==='Обновить серверные сведения')!.trigger('click');await flushPromises()}}
}
async function edit(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){await wrapper.get('[data-timing-edit]').trigger('click');await flushPromises();await wrapper.get('[name="timing_reason"]').setValue('Сверено с документами')}
it('shows unknown facts distinctly from no and obeys server readonly',async()=>{
 const {wrapper}=await open({...initial,timing:{...timing,can_edit:false,notification_sent:false}} as unknown as Expertise)
 expect(wrapper.get('[data-timing-panel]').text()).toContain('Неизвестно');expect(wrapper.get('[data-timing-panel]').text()).toContain('Нет');expect(wrapper.find('[data-timing-edit]').exists()).toBe(false)
})
it('saves reasons, primary and explicit false without changing operational deadlines',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[data-add-timing-reason]').trigger('click');await wrapper.get('[name="timing_delay_reason_id"]').setValue('reason-1')
 expect(wrapper.get('[name="timing_delay_reason_id"]').findAll('option').map(o=>o.attributes('value'))).toEqual(['','reason-1','retained'])
 await wrapper.get('[name="timing_primary_reason"]').setValue('reason-1');await wrapper.get('[name="timing_reasons_complete"]').setValue(true);await wrapper.get('[name="timing_notification_sent"]').setValue('false')
 await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.path).toBe('/api/v1/expertises/work-1/timing/');expect(writes[0]!.body).toEqual({expected_version:1,reason:'Сверено с документами',reasons_complete:true,primary_reason_id:'reason-1',reasons:[{reason_id:'reason-1',comment:'',document_id:null}],notification_sent:false,notification_on:null,notification_document_id:null,extension_requested:null,request_on:null,request_document_id:null,deadline_breached:null,breach_basis:'',breach_document_id:null})
})
it('requires evidence for known sending and evidence plus basis for a negative breach assessment',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[name="timing_notification_sent"]').setValue('true');expect(wrapper.get('[data-timing-submit]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="timing_notification_document_id"]').setValue('notice-doc');await wrapper.get('[name="timing_deadline_breached"]').setValue('false');expect(wrapper.get('[data-timing-submit]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="timing_breach_basis"]').setValue('Письменный срок соблюдён');await wrapper.get('[name="timing_breach_document_id"]').setValue('basis-doc');await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.body).toMatchObject({notification_sent:true,notification_on:null,deadline_breached:false,breach_basis:'Письменный срок соблюдён',breach_document_id:'basis-doc'})
})
it('removes a reason and its primary selection explicitly',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[data-add-timing-reason]').trigger('click');await wrapper.get('[name="timing_delay_reason_id"]').setValue('reason-1');await wrapper.get('[name="timing_primary_reason"]').setValue('reason-1');await wrapper.get('[data-remove-timing-reason]').trigger('click')
 await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises();expect(writes[0]!.body.reasons).toEqual([]);expect(writes[0]!.body.primary_reason_id).toBeNull()
})
it('uploads evidence once, freezes nested preparation and recovers a lost response then a fresh version',async()=>{
 let commands=0
 const state=await open(initial,async w=>{if(w.path==='/api/v1/documents/')return json({...basis,id:'new-doc',kind:'notification',source_kind:'uploaded_copy',versions:[]});if(w.path.endsWith('/versions/'))return json({id:'file-v1',number:1,file_name:'notice.txt',size:6,content_type:'text/plain',uploaded_at:'2026-10-28T01:00:00Z'});commands++;if(commands===1)throw new TypeError('Lost');return commands===2?json({code:'version_conflict',message:'Изменилась версия'},409):json({event:{id:'saved'},expertise:{...initial,version:3}})})
 const {wrapper,writes}=state;await edit(wrapper);await wrapper.get('[name="timing_notification_sent"]').setValue('true');await wrapper.get('[name="timing_notification_document_mode"]').setValue('new');await wrapper.get('[name="document_title"]').setValue('Подтверждение информирования')
 await wrapper.get('[name="source_kind"]').setValue('uploaded_copy');const file=new File(['notice'],'notice.txt',{type:'text/plain'}),input=wrapper.get('[name="basis_file"]');Object.defineProperty(input.element,'files',{value:[file]});await input.trigger('change')
 await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises();expect(wrapper.get('[data-timing-fields]').attributes('disabled')).toBeDefined()
 await wrapper.get('[name="timing_reason"]').setValue('Поздний ввод не меняет повтор');await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises();expect(writes[3]).toEqual(writes[2])
 state.set({...initial,version:2});await state.refresh();await wrapper.get('[data-timing-accept-version]').trigger('click');await wrapper.get('[data-timing-form]').trigger('submit');await flushPromises()
 expect(writes.filter(w=>w.path==='/api/v1/documents/')).toHaveLength(1);expect(writes.filter(w=>w.path.endsWith('/versions/'))).toHaveLength(1);const uploaded=(writes[1]!.body as FormData).get('file') as File;expect(uploaded.name).toBe('notice.txt');expect(await uploaded.text()).toBe('notice');expect((writes[1]!.body as FormData).get('expected_version')).toBe('1');expect(writes[4]!.body.expected_version).toBe(2);expect(writes[4]!.body.notification_document_id).toBe('new-doc');expect(writes[4]!.key).not.toBe(writes[2]!.key)
})
it('shows document-only reason history readably',async()=>{
 const record={reason:reasonRef,comment:'Причина по материалам',document_id:'old-evidence'}
 const current={...initial,timing:{...timing,revisions:[{id:'r1',number:1,actor:{id:'a',full_name:'Эксперт'},created_at:'2026-10-28T01:00:00Z',reason:'Заменена ссылка',before:{reasons:[record]},after:{reasons:[{...record,document_id:'new-evidence'}]}}]}} as unknown as Expertise
 const {wrapper}=await open(current);const text=wrapper.get('[data-timing-panel] .subsection').text();expect(text).toContain('Загруженность экспертов');expect(text).toContain('old-evidence');expect(text).toContain('new-evidence');expect(text).not.toContain('"report_group"')
})
it('keeps a forbidden draft and guards route leave',async()=>{
 const state=await open(initial,()=>json({message:'Нет прав'},403));await edit(state.wrapper);await state.wrapper.get('[data-timing-form]').trigger('submit');await flushPromises();expect(state.wrapper.text()).toContain('Нет прав')
 vi.spyOn(window,'confirm').mockReturnValue(false);await state.router.push('/expertises');expect(state.router.currentRoute.value.path).toBe('/expertises/work-1')
})
it('ignores a late reply after switching cards',async()=>{
 let finish!:(response:Response)=>void
 const state=await open(initial,()=>new Promise<Response>(resolve=>{finish=resolve}));await edit(state.wrapper);await state.wrapper.get('[data-timing-form]').trigger('submit');await flushPromises();vi.spyOn(window,'confirm').mockReturnValue(true)
 state.set({...initial,id:'work-2',registration_number:'152/4-1-26'});await state.router.push('/expertises/work-2');await flushPromises();finish(json({event:{id:'late'},expertise:{...initial,version:2}}));await flushPromises();expect(state.wrapper.get('h1').text()).toBe('152/4-1-26')
})
