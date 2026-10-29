import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import {createMemoryHistory,createRouter} from 'vue-router'
import {ApiClient,apiKey} from '../../api/client'
import {json,sessionWith} from '../../test/fixtures'
import {basis} from '../../test/intakeFixtures'
enableAutoUnmount(afterEach);afterEach(()=>{vi.restoreAllMocks();vi.useRealTimers()})
const specialty={id:'spec-1',code:'1.1',name:'Почерковедческая',is_active:true,version:1}
const refs=[specialty,{...specialty,id:'spec-2',code:'16.1',name:'Строительная'},{...specialty,id:'retained',code:'old',name:'Ранее использовалась',is_active:false},{...specialty,id:'forbidden',code:'new-inactive',name:'Не использовалась',is_active:false}]
const empty={id:null,year:2027,total:null,basis_text:'',document_id:null,document:null,version:0,lines:[],revisions:[],can_edit:true,specialties:refs,retained_specialty_ids:['retained']}
const seeded={...empty,id:'plan-2026',year:2026,total:294,basis_text:'План подтверждён владельцем',version:1,lines:[{id:'line-1',specialty,count:0},{id:'line-2',specialty:refs[1],count:null}],revisions:[{id:'system',number:1,actor:null,created_at:'2026-10-28T01:00:00Z',reason:'Подтверждение владельца',before:{total:null},after:{total:294}}]}
type Write={path:string;body:any;key:string|null}
async function open(options:{actions?:string[];initial?:string;current?:any;respond?:(w:Write,n:number)=>Response|Promise<Response>;get?:(path:string)=>Response|Promise<Response>}={}){
 const component=(await import('./ReportPlansPage.vue')).default,paths:string[]=[],writes:Write[]=[]
 let current=options.current??empty
 const pinia=sessionWith(...(options.actions??['reports.plans.manage','documents.view','documents.upload']))
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/report-plans',component},{path:'/reports',component:{template:'<p>Отчёт</p>'}},{path:'/workspace',component:{template:'<p>Рабочее место</p>'}}]})
 await router.push(options.initial??'/report-plans?year=2027');await router.isReady()
 const wrapper=mount(component,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:new ApiClient(async(input,init)=>{
  const path=String(input);paths.push(path);if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
  if(init?.method==='POST'){const w={path,body:init.body instanceof FormData?init.body:JSON.parse(String(init.body)),key:new Headers(init.headers).get('Idempotency-Key')};writes.push(w);return options.respond?options.respond(w,writes.length):json({...current,id:'plan-2027',version:1})}
  return options.get?options.get(path):json(current)
 })}}});await flushPromises();return {wrapper,router,pinia,paths,writes,set:(next:any)=>{current=next}}
}
async function edit(wrapper:Awaited<ReturnType<typeof open>>['wrapper']){await wrapper.get('[data-plan-edit]').trigger('click');await wrapper.get('[name="plan_reason"]').setValue('Сверено с утверждённым планом')}
it('shows a read-only confirmed plan, zero, unknown and system history without offering a write',async()=>{
 const {wrapper}=await open({current:{...seeded,can_edit:false},initial:'/report-plans?year=2026',actions:['reports.form151.run']})
 expect(wrapper.get('h1').text()).toContain('Годовые планы');expect(wrapper.text()).toContain('294');expect(wrapper.text()).toContain('Неизвестно');expect(wrapper.text()).toContain('Система')
 expect(wrapper.find('[data-plan-edit]').exists()).toBe(false);expect(wrapper.get('[data-plan-lines]').text()).toContain('0')
})
it('defaults to the current institution year and keeps other query fields when opening another year',async()=>{
 vi.useFakeTimers({toFake:['Date']});vi.setSystemTime(new Date('2026-10-28T01:00:00Z'))
 const state=await open({initial:'/report-plans?view=kept',current:{...empty,year:2026}})
 expect(state.paths).toContain('/api/v1/report-plans/2026/');expect(state.wrapper.get('[name="plan_year"]').element).toHaveProperty('value','2026')
 await state.wrapper.get('[name="plan_year"]').setValue('2028');await state.wrapper.get('.year-picker').trigger('submit');await flushPromises()
 expect(state.router.currentRoute.value.query).toEqual({view:'kept',year:'2028'});expect(state.paths).toContain('/api/v1/report-plans/2028/')
})
it('does not silently choose a year from a repeated or malformed URL',async()=>{
 for(const initial of ['/report-plans?year=2026&year=2027','/report-plans?year=1899','/report-plans?year=oops']){
  const state=await open({initial});expect(state.paths).toEqual([]);expect(state.wrapper.find('[data-plan-editor]').exists()).toBe(false);state.wrapper.unmount()
 }
})
it('does not request or show institutional plans for a department-only reporting grant',async()=>{
 const {wrapper,paths,pinia}=await open({actions:[]});const session=(await import('../../stores/session')).useSessionStore(pinia)
 session.user!.access['reports.form151.run']=[{scope:'departments',scope_limit:'institution',department_ids:['dept'],role_id:'r',role_name:'Отдел',assignment_id:'a'}]
 await flushPromises();expect(paths).toEqual([]);expect(wrapper.find('[data-plan-edit]').exists()).toBe(false)
})
it('creates a year with a full packet, keeps zero/null distinct and reports the unallocated balance',async()=>{
 const {wrapper,writes}=await open();await edit(wrapper);await wrapper.get('[name="plan_total"]').setValue('10');await wrapper.get('[name="plan_basis_text"]').setValue('Приказ об утверждении плана')
 await wrapper.get('[data-plan-add-line]').trigger('click');await wrapper.findAll('[name="plan_specialty_id"]')[0]!.setValue('spec-1');await wrapper.findAll('[name="plan_count"]')[0]!.setValue('0')
 await wrapper.get('[data-plan-add-line]').trigger('click');await wrapper.findAll('[name="plan_specialty_id"]')[1]!.setValue('spec-2')
 expect(wrapper.get('[data-plan-balance]').text()).toContain('10');expect(wrapper.findAll('[name="plan_specialty_id"]')[0]!.findAll('option').map(o=>o.attributes('value'))).toEqual(['','spec-1','spec-2','retained'])
 await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 expect(writes[0]).toMatchObject({path:'/api/v1/report-plans/2027/',body:{expected_version:0,reason:'Сверено с утверждённым планом',total:10,basis_text:'Приказ об утверждении плана',document_id:null,lines:[{specialty_id:'spec-1',count:0},{specialty_id:'spec-2',count:null}]}})
})
it('retains an exact lost-response packet and does not send a changed year or draft on retry',async()=>{
 let commands=0;const {wrapper,writes}=await open({respond:()=>{commands++;if(commands===1)throw new TypeError('Lost reply');return json({...empty,id:'saved',version:1})}})
 await edit(wrapper);await wrapper.get('[name="plan_total"]').setValue('0');await wrapper.get('[name="plan_basis_text"]').setValue('Подтверждённый нулевой план');await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 expect(wrapper.get('[data-plan-fields]').attributes('disabled')).toBeDefined();await wrapper.get('[name="plan_total"]').setValue('99')
 await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises();expect(writes[1]).toEqual(writes[0]);expect(writes[1]!.body.total).toBe(0)
})
it('refreshes a conflicting version without replacing the draft, then requires explicit acceptance',async()=>{
 let commands=0;const state=await open({current:{...empty,id:'plan',version:1},respond:()=>++commands===1?json({code:'version_conflict',message:'План изменён'},409):json({...empty,id:'plan',version:3})})
 await edit(state.wrapper);await state.wrapper.get('[name="plan_total"]').setValue('10');await state.wrapper.get('[name="plan_basis_text"]').setValue('Моё основание');await state.wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 state.set({...empty,id:'plan',version:2,total:7,basis_text:'Чужая редакция'});await state.wrapper.get('[data-plan-refresh]').trigger('click');await flushPromises()
 expect(state.wrapper.get('[name="plan_total"]').element).toHaveProperty('value','10');expect(state.wrapper.get('[data-plan-submit]').attributes('disabled')).toBeDefined()
 await state.wrapper.get('[data-plan-accept-version]').trigger('click');await state.wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 expect(state.writes[1]!.body).toMatchObject({expected_version:2,total:10,basis_text:'Моё основание'});expect(state.writes[1]!.key).not.toBe(state.writes[0]!.key)
})
it('keeps a forbidden draft and guards year navigation; accepted navigation ignores an old response',async()=>{
 let finish!:(r:Response)=>void
 const {wrapper,router}=await open({respond:()=>new Promise<Response>(r=>{finish=r})})
 await edit(wrapper);vi.spyOn(window,'confirm').mockReturnValue(false);await router.push('/report-plans?year=2028');expect(router.currentRoute.value.query.year).toBe('2027')
 await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises();vi.mocked(window.confirm).mockReturnValue(true);await router.push('/report-plans?year=2028');await flushPromises()
 finish(json({...empty,year:2027,total:777,version:1}));await flushPromises();expect(wrapper.text()).not.toContain('777');expect(router.currentRoute.value.query.year).toBe('2028')
})
it('preserves input on403 and a late old-year GET cannot replace the next year',async()=>{
 const forbidden=await open({respond:()=>json({message:'Нет права на план'},403)});await edit(forbidden.wrapper);await forbidden.wrapper.get('[name="plan_total"]').setValue('0');await forbidden.wrapper.get('[name="plan_basis_text"]').setValue('Основание');await forbidden.wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 expect(forbidden.wrapper.text()).toContain('Нет права на план');expect(forbidden.wrapper.get('[name="plan_total"]').element).toHaveProperty('value','0');forbidden.wrapper.unmount()
 let finish!:(r:Response)=>void
 const state=await open({get:path=>path.includes('/2027/')?new Promise<Response>(r=>{finish=r}):json({...empty,year:2028,total:8})})
 await state.router.push('/report-plans?year=2028');await flushPromises();finish(json({...empty,total:777}));await flushPromises();expect(state.wrapper.text()).not.toContain('777')
})
it('uploads an actual file and reconciles document409 without recreating the document or changing the plan version',async()=>{
 let uploads=0;const prior={id:'prior',number:1,original_name:'prior.txt',content_type:'text/plain',size:5,sha256:'abc',created_at:'2026-10-28T01:00:00Z',download_url:'/download/',preview_url:null}
 const {wrapper,writes}=await open({respond:w=>{
  if(w.path==='/api/v1/documents/')return json({...basis,id:'new-doc',kind:'letter',source_kind:'uploaded_copy',versions:[]})
  if(w.path.endsWith('/versions/'))return ++uploads===1?json({code:'version_conflict',message:'Документ изменён'},409):json({...prior,id:'my-file',number:2,original_name:'plan.txt'})
  return json({...empty,id:'plan',version:1})
 },get:path=>path.includes('/documents/')?json({...basis,id:'new-doc',kind:'letter',source_kind:'uploaded_copy',version:2,versions:[prior]}):json(empty)})
 await edit(wrapper);await wrapper.get('[name="plan_total"]').setValue('10');await wrapper.get('[data-document-new]').trigger('click');await wrapper.get('[name="document_title"]').setValue('План госзадания');await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
 const input=wrapper.get('[name="basis_file"]');Object.defineProperty(input.element,'files',{value:[new File(['plan'],'plan.txt',{type:'text/plain'})]});await input.trigger('change')
 await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises();expect(writes.filter(w=>w.path.includes('/report-plans/'))).toHaveLength(0)
 expect(wrapper.get('[data-plan-submit]').attributes('disabled')).toBeDefined();await wrapper.get('[data-refresh-document-version]').trigger('click');await flushPromises();expect(wrapper.text()).toContain('prior.txt')
 await wrapper.get('[data-accept-document-version]').trigger('click');await wrapper.get('[data-plan-form]').trigger('submit');await flushPromises()
 expect(writes.filter(w=>w.path==='/api/v1/documents/')).toHaveLength(1);const files=writes.filter(w=>w.path.endsWith('/versions/'));expect(files).toHaveLength(2);expect((files[1]!.body as FormData).get('expected_version')).toBe('2');expect((files[1]!.body as FormData).get('file')).toBeInstanceOf(File)
 expect(await ((files[1]!.body as FormData).get('file') as File).text()).toBe('plan');expect(writes.find(w=>w.path.includes('/report-plans/'))!.body).toMatchObject({expected_version:0,document_id:'new-doc',total:10})
})
