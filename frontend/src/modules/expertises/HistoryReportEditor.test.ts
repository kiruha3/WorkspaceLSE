import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { ApiClient,apiKey } from '../../api/client'
import type { Expertise,HistoricalWork } from '../../api/types'
import { json,sessionWith } from '../../test/fixtures'
import { expertise,specialty,testRouter } from '../../test/intakeFixtures'
import ExpertisePage from './ExpertisePage.vue'

enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const reference=(id:string,code=id)=>({id,code,name:`Причина ${code}`,is_active:true,version:1})
const options={specialties:[specialty],sndz_reasons:[reference('sndz','science_cannot_answer')],return_reasons:[reference('return','appointing_party_request')],unresolved_reasons:[reference('materials','materials_insufficient'),reference('other','other')]}
const history:HistoricalWork={id:'history',operational:false,complex_known:false,composition_known:false,suspension_history_complete:false,statistics_confirmed:false,result_kind:'expert_conclusion',completed_on:'2026-10-06',return_decided_on:null,issued_on:null,complexity_level:1,questions:2,categorical:2,probable:null,unresolved:0,amount:null,authority_type:'',authority_name:'',official:'',contact:'',basis_text:'',case_description:'',inventory:'',executor_raw:'Эксперт в источнике',unresolved_note:'',unresolved_reason_raw:'',notes:'',delivery:'',current_participants:[],source:{batch_id:'batch',row_id:'row',source_row:4,origin_url:null,source_observed_at:null},report_gaps:[]}
const work:Expertise={...expertise,origin_kind:'historical',historical:history,state:'completed',version:1,allowed_actions:['expertise.closed.correct'],basis_document:null,receipt:{...expertise.receipt,received_at:'2026-10-01',status:'historical'}}
type Write={path:string;body:any;key:string|null}
async function open(initial=work,respond?:(write:Write,n:number)=>Response|Promise<Response>){
  let current=initial;const writes:Write[]=[];const gets:string[]=[];const router=await testRouter('/expertises/work-1')
  const wrapper=mount(ExpertisePage,{global:{plugins:[sessionWith('expertise.view','expertise.closed.correct'),router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.method==='POST'){
      const write={path,body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(write)
      return respond?respond(write,writes.length):json({event:{id:'correction'},expertise:{...current,version:current.version+1}})
    }
    gets.push(path);return json(path.endsWith('/history-report/')?options:current)
  })}}})
  await flushPromises();return {wrapper,writes,gets,router,set:(next:Expertise)=>{current=next},refresh:async()=>{await wrapper.findAll('button').find(b=>b.text()==='Обновить серверные сведения')!.trigger('click');await flushPromises()}}
}
async function edit(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){
  await wrapper.get('[data-history-report-edit]').trigger('click');await flushPromises()
  await wrapper.get('[name="history_report_reason"]').setValue('  Сверено по материалам  ')
}

it('offers correction only for the authoritative historical closed action',async()=>{
  for(const current of [{...work,allowed_actions:[]},{...work,state:'in_progress' as const},{...work,historical:{...history,operational:true}}]){
    const {wrapper,gets}=await open(current)
    expect(wrapper.find('[data-history-report-edit]').exists()).toBe(false)
    expect(gets.some(path=>path.endsWith('/history-report/'))).toBe(false)
    wrapper.unmount()
  }
})

it('keeps a missing edit right visible while its general explanation is optional help',async()=>{
  const {wrapper,gets}=await open({...work,allowed_actions:[]})
  expect(wrapper.get('[data-history-report-panel]').text()).toContain('Редактирование недоступно для ваших прав.')
  expect(wrapper.find('[data-history-report-edit]').exists()).toBe(false)
  expect(gets.some(path=>path.endsWith('/history-report/'))).toBe(false)
})

it('saves archival counts and specialty with explicit nulls and zero without native completion',async()=>{
  const {wrapper,writes}=await open();await edit(wrapper)
  await wrapper.get('[name="history_report_questions"]').setValue('')
  await wrapper.get('[name="history_report_categorical"]').setValue('0')
  await wrapper.get('[name="history_report_completed_on"]').setValue('')
  await wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(writes).toHaveLength(1);expect(writes[0]!.path).toBe('/api/v1/expertises/work-1/history-report/')
  expect(writes[0]!.body).toMatchObject({expected_version:1,reason:'Сверено по материалам',specialty_id:specialty.id,correction_kind:'result',result:{completed_on:null,questions:null,categorical:0,probable:null,unresolved:0,statistics_complete:false}})
  expect(writes[0]!.body.result).not.toHaveProperty('document_id')
  expect(wrapper.text()).toContain('Уточнение сохранено. Номер и состояние работы не изменены.')
})

it('records return decision separately and does not invent an absent decision date',async()=>{
  const {wrapper,writes}=await open({...work,state:'without_execution',historical:{...history,completed_on:null,result_kind:null}});await edit(wrapper)
  expect(wrapper.find('[name="history_report_questions"]').exists()).toBe(false)
  await wrapper.get('[name="history_report_return_reason"]').setValue('return')
  await wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(writes[0]!.body).toMatchObject({correction_kind:'return',return_data:{decided_on:null,return_reason_id:'return',comment:''}})
  expect(writes[0]!.body).not.toHaveProperty('result')
})

it('freezes an uncertain packet and reuses exactly its body and key',async()=>{
  const {wrapper,writes}=await open(work,async(_,n)=>{if(n===1)throw new TypeError('Connection lost');return json({event:{id:'same'},expertise:{...work,version:2}})})
  await edit(wrapper);await wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(wrapper.get('[data-history-report-form] fieldset').attributes('disabled')).toBeDefined()
  await wrapper.get('[name="history_report_reason"]').setValue('Попытка изменения после потери ответа')
  await wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0])
  expect(wrapper.find('[data-history-report-form]').exists()).toBe(false)
})

it('retains input after conflict and requires explicit adoption of a refreshed version',async()=>{
  const state=await open(work,async(_,n)=>n===1?json({code:'command_conflict',message:'Карточка изменена'},409):json({event:{id:'new'},expertise:{...work,version:3}}))
  await edit(state.wrapper);await state.wrapper.get('[name="history_report_complexity"]').setValue('3')
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  state.set({...work,version:2});await state.refresh()
  expect((state.wrapper.get('[name="history_report_complexity"]').element as HTMLInputElement).value).toBe('3')
  await state.wrapper.get('[data-history-report-accept-version]').trigger('click')
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(state.writes[1]!.body.expected_version).toBe(2);expect(state.writes[1]!.key).not.toBe(state.writes[0]!.key)
})

it('recovers a frozen lost attempt after a definitive stale version response',async()=>{
  const state=await open(work,async(_,n)=>{if(n===1)throw new TypeError('Lost before commit');if(n===2)return json({code:'version_conflict',message:'Изменена версия'},409);return json({event:{id:'new'},expertise:{...work,version:3}})})
  await edit(state.wrapper);await state.wrapper.get('[name="history_report_complexity"]').setValue('3')
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(state.writes[1]).toEqual(state.writes[0])
  expect(state.wrapper.get('[data-history-report-form] fieldset').attributes('disabled')).toBeUndefined()
  state.set({...work,version:2});await state.refresh()
  await state.wrapper.get('[data-history-report-accept-version]').trigger('click')
  expect((state.wrapper.get('[name="history_report_complexity"]').element as HTMLInputElement).value).toBe('3')
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  expect(state.writes[2]!.body.expected_version).toBe(2);expect(state.writes[2]!.key).not.toBe(state.writes[0]!.key)
})

it('does not discard a draft when the grant disappears',async()=>{
  const state=await open();await edit(state.wrapper)
  state.set({...work,allowed_actions:[]});await state.refresh()
  expect(state.wrapper.find('[data-history-report-form]').exists()).toBe(true)
  expect((state.wrapper.get('[name="history_report_reason"]').element as HTMLTextAreaElement).value).toContain('Сверено')
  expect(state.wrapper.get('[data-history-report-submit]').attributes('disabled')).toBeDefined()
})

it('ignores a late correction response after moving to a different card',async()=>{
  vi.spyOn(window,'confirm').mockReturnValue(true);let resolve!:(response:Response)=>void
  const state=await open(work,async()=>new Promise<Response>(r=>{resolve=r}));await edit(state.wrapper)
  await state.wrapper.get('[data-history-report-form]').trigger('submit');await flushPromises()
  state.set({...work,id:'work-2',registration_number:'152/3-1-26'});await state.router.push('/expertises/work-2');await flushPromises()
  resolve(json({event:{id:'old'},expertise:{...work,version:2}}));await flushPromises()
  expect(state.wrapper.get('h1').text()).toBe('152/3-1-26')
  expect(state.wrapper.text()).not.toContain('Уточнение сохранено.')
})

it('shows the recorded correction author and readable before-after references',async()=>{
  const corrected={...work,historical:{...history,corrections:[{id:'correction',number:1,actor:{id:'actor',full_name:'Ответственный эксперт'},created_at:'2026-10-28T04:00:00Z',reason:'Сверено с заключением',before:{specialty:{id:'old',code:'18.1',name:'Стоимость ТС'},categorical:null},after:{specialty:{id:specialty.id,code:'1.1',name:'Почерковедческая'},categorical:0}}]}}
  const {wrapper}=await open(corrected)
  expect(wrapper.get('[data-history-corrections]').text()).toContain('Ответственный эксперт')
  expect(wrapper.get('[data-history-corrections]').text()).toContain('18.1 · Стоимость ТС')
  expect(wrapper.get('[data-history-corrections]').text()).toContain('1.1 · Почерковедческая')
  expect(wrapper.get('[data-history-corrections]').text()).toContain('Неизвестно')
})

it('shows a known return reason even while the decision date is still unknown',async()=>{
  const returned={...work,state:'without_execution' as const,allowed_actions:[],historical:{...history,result_kind:null,completed_on:null,return_decided_on:null,report_details:{sndz_reason:null,sndz_comment:'',allocations_complete:false,note:'',unresolved_allocations:[],return_reason:reference('return','appointing_party_request'),return_comment:'Подтверждено запросом органа'}}}
  const {wrapper}=await open(returned)
  expect(wrapper.get('[data-history-report-panel]').text()).toContain('Подтверждено запросом органа')
})

it('keeps the recorded correction history readable after activation and reload',async()=>{
  const current={...work,historical:{...history,corrections:[{id:'c',number:1,actor:{id:'actor',full_name:'Ответственный эксперт'},created_at:'2026-10-28T04:00:00Z',reason:'Уточнена причина до перехода',before:{categorical:null},after:{categorical:0}}]}}
  const state=await open(current)
  state.set({...current,historical:{...current.historical,operational:true},allowed_actions:[]});await state.refresh()
  expect(state.wrapper.get('[data-history-corrections]').text()).toContain('Уточнена причина до перехода')
  expect(state.wrapper.find('[data-history-report-edit]').exists()).toBe(false)
  await state.refresh();expect(state.wrapper.get('[data-history-corrections]').text()).toContain('Ответственный эксперт')
})
