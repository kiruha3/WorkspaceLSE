import { enableAutoUnmount,flushPromises,mount } from '@vue/test-utils'
import { afterEach,expect,it } from 'vitest'
import { createMemoryHistory,createRouter } from 'vue-router'
import { ApiClient,apiKey } from '../../api/client'
import { json,sessionWith } from '../../test/fixtures'
import { useSessionStore } from '../../stores/session'
import JournalSyncActions from './JournalSyncActions.vue'

enableAutoUnmount(afterEach)
const source={configured:true,spreadsheet_id:'source-123456789',gid:'0',sheet_name:'Лист1',label:'Журнал',url:'https://docs.google.com/spreadsheets/d/source-123456789/edit'}
async function open(transport:typeof fetch,codes=['imports.preview','imports.results.view']){
 const pinia=sessionWith(...codes);useSessionStore(pinia).user!.supported_modules=['journal_import_preview','journal_application','journal_google_preview']
 const router=createRouter({history:createMemoryHistory(),routes:[{path:'/expertises',component:{template:'<p>Реестр</p>'}},{path:'/imports',component:{template:'<p>Источники</p>'}},{path:'/imports/:id/review',component:{template:'<p>Перечень</p>'}}]})
 await router.push('/expertises?department_id=d3&page=2')
 const api=new ApiClient(async(input,init)=>String(input).includes('/csrf/')?json({csrf_token:'t'}):transport(input,init))
 const wrapper=mount(JournalSyncActions,{global:{plugins:[pinia,router],provide:{[apiKey as symbol]:api}}});await flushPromises()
 return {wrapper,router}
}

it('uploads the selected file into a preview and opens review without applying business records',async()=>{
 const posts:{path:string;fileName:string;reason:string;key:string|null}[]=[]
 const {wrapper,router}=await open(async(input,init)=>{
  const body=init!.body as FormData
  posts.push({path:String(input),fileName:(body.get('file') as File).name,reason:String(body.get('reason')),key:new Headers(init!.headers).get('Idempotency-Key')})
  return json({batch:{id:'file-batch'}},201)
 })
 await wrapper.get('[data-upload-journal-file]').trigger('click')
 const input=wrapper.get('[name="journal_sync_file"]')
 Object.defineProperty(input.element,'files',{value:[new File(['csv-content'],'journal.csv',{type:'text/csv'})],configurable:true})
 await input.trigger('change');await wrapper.get('[data-journal-file-form]').trigger('submit');await flushPromises()
 expect(posts,wrapper.text()).toHaveLength(1);expect(posts[0]!.path).toBe('/api/v1/imports/preview/');expect(posts[0]!.fileName).toBe('journal.csv');expect(posts[0]!.key).toBeTruthy();expect(posts[0]!.reason).toBeTruthy()
 expect(router.currentRoute.value.path).toBe('/imports/file-batch/review')
 expect(router.currentRoute.value.query.return).toBe('/expertises?department_id=d3&page=2')
})

it('retries a lost Google preview response with the same source, body and key',async()=>{
 const writes:{body:unknown;key:string|null}[]=[]
 const {wrapper}=await open(async(input,init)=>{
  if(String(input).includes('/google-source/'))return json(source)
  writes.push({body:JSON.parse(String(init?.body)),key:new Headers(init?.headers).get('Idempotency-Key')})
  if(writes.length===1)throw new TypeError('Lost response')
  return json({batch:{id:'b1'}},201)
 })
 await wrapper.get('[data-read-journal-source]').trigger('click');await flushPromises()
 expect(wrapper.get('[data-read-journal-source]').attributes('disabled')).toBeDefined()
 const retry=wrapper.findAll('button').find(button=>button.text()==='Повторить ту же попытку')!
 await retry.trigger('click');await flushPromises()
 expect(writes).toHaveLength(2);expect(writes[1]).toEqual(writes[0])
})

it('does not replay an earlier failed write when a fresh source metadata read fails',async()=>{
 let reads=0
 const {wrapper}=await open(async(input)=>{
  if(String(input).includes('/google-source/')){if(++reads===2)throw new TypeError('Read offline');return json(source)}
  return json({code:'invalid_source',message:'Проверьте источник'},400)
 })
 await wrapper.get('[data-read-journal-source]').trigger('click');await flushPromises()
 await wrapper.get('[data-read-journal-source]').trigger('click');await flushPromises()
 expect(wrapper.text()).not.toContain('Повторить ту же попытку')
 expect(wrapper.get('[data-read-journal-source]').attributes('disabled')).toBeUndefined()
})

it('does not expose source mutations without preview permission',async()=>{
 const {wrapper}=await open(async()=>json(source),['imports.results.view'])
 expect(wrapper.find('[data-read-journal-source]').exists()).toBe(false)
 expect(wrapper.find('[data-upload-journal-file]').exists()).toBe(false)
})
