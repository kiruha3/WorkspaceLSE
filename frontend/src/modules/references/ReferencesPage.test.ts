import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it,vi } from 'vitest'
import { createMemoryHistory,createRouter } from 'vue-router'
import App from '../../App.vue'
import { router as productionRouter } from '../../router'
import { ApiClient,apiKey } from '../../api/client'
import { json,page,sessionWith } from '../../test/fixtures'
enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const item={id:'type-1',code:'sk',name:'Следственные органы СК РФ',is_active:true,version:1,report_group:'sk'}
type Write={path:string;body:any;key:string|null}
async function open(codes=['references.view','references.manage'],respond?:(w:Write,n:number)=>Response|Promise<Response>){
 let rows=[item]
 const pinia=sessionWith(...codes),router=createRouter({history:createMemoryHistory(),routes:productionRouter.options.routes});const writes:Write[]=[],gets:string[]=[]
 const wrapper=mount(App,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
  const path=String(input);if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
  if(init?.method==='POST'||init?.method==='PATCH'){const w={path,body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(w);return respond?respond(w,writes.length):json({...item,...w.body,version:2})}
  gets.push(path);if(path.includes('/history/'))return json([{id:'audit',action:'reference.update',actor:{id:'u',full_name:'Ответственный'},created_at:'2026-10-28T00:00:00Z',reason:'По приказу',changes:{before:{name:'Прежнее'},after:{name:'Новое'}}}])
  if(path.includes('/departments/'))return json(page([{id:'d-4',code:'4',name:'Отдел 4',is_active:true,version:1}]))
  if(path.includes('search=missing'))return json(page([]))
  return json(page(rows))
 })}}});await router.push('/references');await router.isReady();await flushPromises();return {wrapper,router,writes,gets,set:(next:typeof rows)=>{rows=next}}
}
async function create(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){
 await wrapper.get('[name="catalog"]').setValue('authority-types');await flushPromises();await wrapper.get('[data-reference-create]').trigger('click')
 await wrapper.get('[name="reference_code"]').setValue('DEMO');await wrapper.get('[name="reference_name"]').setValue('Новый тип')
}
it('opens all catalogues read-only without a management grant',async()=>{
 const {wrapper}=await open(['references.view']);expect(wrapper.get('h1').text()).toBe('Справочники');expect(wrapper.get('[name="catalog"]').findAll('option')).toHaveLength(13);expect(wrapper.find('[data-reference-create]').exists()).toBe(false)
 await wrapper.get('[data-reference-history]').trigger('click');await flushPromises();expect(wrapper.text()).toContain('Ответственный');expect(wrapper.text()).toContain('Прежнее')
})
it('creates an authority with an explicit unknown report group rather than other',async()=>{
 const {wrapper,writes}=await open();await create(wrapper);await wrapper.get('[data-reference-form]').trigger('submit');await flushPromises()
 expect(writes[0]!.path).toBe('/api/v1/references/authority-types/');expect(writes[0]!.body).toEqual({code:'DEMO',name:'Новый тип',report_group:null});expect(writes[0]!.key).toBeTruthy()
})
it('creates a delay reason with a distinct explicit reporting mapping',async()=>{
 const {wrapper,writes}=await open();await wrapper.get('[name="catalog"]').setValue('delay-reasons');await flushPromises();await wrapper.get('[data-reference-create]').trigger('click')
 await wrapper.get('[name="reference_code"]').setValue('custom-delay');await wrapper.get('[name="reference_name"]').setValue('Подтверждённая особая причина');await wrapper.get('[name="reference_report_group"]').setValue('expert_workload')
 await wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(writes[0]!.path).toBe('/api/v1/references/delay-reasons/');expect(writes[0]!.body.report_group).toBe('expert_workload')
})
it('edits name, active and group without changing the stable code',async()=>{
 const {wrapper,writes}=await open();await wrapper.get('[name="catalog"]').setValue('authority-types');await flushPromises();await wrapper.get('[data-reference-edit]').trigger('click')
 expect(wrapper.find('[name="reference_code"]').exists()).toBe(false);await wrapper.get('[name="reference_name"]').setValue('Новое имя');await wrapper.get('[name="reference_active"]').setValue(false);await wrapper.get('[name="reference_report_group"]').setValue('court')
 await wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(writes[0]!.body).toEqual({expected_version:1,name:'Новое имя',is_active:false,report_group:'court'});expect(writes[0]!.path).toBe('/api/v1/references/authority-types/type-1/')
})
it('includes immutable creation-only subtype fields for journals and closure rules',async()=>{
 const {wrapper,writes}=await open();await wrapper.get('[name="catalog"]').setValue('letter-journals');await flushPromises();await wrapper.get('[data-reference-create]').trigger('click');await flushPromises()
 await wrapper.get('[name="reference_code"]').setValue('DEMO-IN');await wrapper.get('[name="reference_name"]').setValue('Учебный входящий');await wrapper.get('[name="reference_direction"]').setValue('incoming');await wrapper.get('[name="reference_department"]').setValue('d-4')
 await wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(writes[0]!.body).toMatchObject({direction:'incoming',department_id:'d-4'})
 await wrapper.get('[name="catalog"]').setValue('control-closure-reasons');await flushPromises();await wrapper.get('[data-reference-create]').trigger('click');await wrapper.get('[name="reference_code"]').setValue('DEMO-ANSWER');await wrapper.get('[name="reference_name"]').setValue('Учебная причина');await wrapper.get('[name="reference_rule"]').setValue('reply_sent')
 await wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(writes[1]!.body.rule).toBe('reply_sent')
})
it('freezes a lost create packet and recovers a definitive 400 without duplicate keys',async()=>{
 const state=await open(undefined,async(_,n)=>{if(n===1)throw new TypeError('Lost');if(n===2)return json({message:'Код занят'},400);return json(item)})
 await create(state.wrapper);await state.wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(state.wrapper.get('[data-reference-fields]').attributes('disabled')).toBeDefined()
 await state.wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(state.writes[1]).toEqual(state.writes[0]);expect(state.wrapper.text()).toContain('Код занят')
 await state.wrapper.get('[name="reference_code"]').setValue('DEMO-2');await state.wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(state.writes[2]!.body.code).toBe('DEMO-2');expect(state.writes[2]!.key).not.toBe(state.writes[0]!.key)
})
it('keeps a dirty editor when switching catalog is cancelled and searches by query',async()=>{
 const {wrapper,gets}=await open();await create(wrapper);vi.spyOn(window,'confirm').mockReturnValue(false);await wrapper.get('[name="catalog"]').setValue('positions');await flushPromises();expect(wrapper.find('[data-reference-form]').exists()).toBe(true)
 expect((wrapper.get('[name="catalog"]').element as HTMLSelectElement).value).toBe('authority-types')
 await wrapper.get('[data-reference-cancel]').trigger('click');vi.mocked(window.confirm).mockReturnValue(true);await wrapper.get('[data-reference-cancel]').trigger('click');await wrapper.get('[name="reference_search"]').setValue('суд');await wrapper.get('[data-reference-search]').trigger('submit');await flushPromises();expect(gets.some(p=>p.includes('search=%D1%81%D1%83%D0%B4'))).toBe(true)
})
it('shows reports for the registry role without requiring import permission',async()=>{
 const {wrapper}=await open(['reports.form151.run','expertise.view']);expect(wrapper.find('a[href="/reports"]').exists()).toBe(true);expect(wrapper.find('a[href="/references"]').exists()).toBe(false);expect(wrapper.text()).not.toContain('Следом — импорт и отчётность')
})
it('refreshes a conflicted item even when the current list filter hides it',async()=>{
 const state=await open(undefined,(_,n)=>n===1?json({message:'Версия изменилась'},409):json({...item,version:3}))
 await state.wrapper.get('[name="catalog"]').setValue('authority-types');await flushPromises();await state.wrapper.get('[data-reference-edit]').trigger('click');await state.wrapper.get('[name="reference_name"]').setValue('Мой исправленный тип')
 await state.wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();state.set([{...item,version:2}])
 await state.wrapper.get('[name="reference_search"]').setValue('missing');await state.wrapper.get('[data-reference-search]').trigger('submit');await flushPromises()
 await state.wrapper.findAll('button').find(b=>b.text()==='Обновить серверную запись')!.trigger('click');await flushPromises();await state.wrapper.get('[data-reference-accept-version]').trigger('click')
 await state.wrapper.get('[data-reference-form]').trigger('submit');await flushPromises();expect(state.writes[1]!.body).toMatchObject({expected_version:2,name:'Мой исправленный тип'});expect(state.writes[1]!.key).not.toBe(state.writes[0]!.key)
})
