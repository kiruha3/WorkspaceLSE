import {flushPromises,mount,enableAutoUnmount} from '@vue/test-utils'
import {afterEach,expect,it,vi} from 'vitest'
import {ApiClient,apiKey} from '../api/client'
import type {BasisDocument} from '../api/types'
import {basis} from '../test/intakeFixtures'
import {json,page,sessionWith} from '../test/fixtures'
import DocumentPicker from './DocumentPicker.vue'
import {useSessionStore} from '../stores/session'
enableAutoUnmount(afterEach);afterEach(()=>vi.restoreAllMocks())
const doc:BasisDocument={...basis,id:'doc-a',title:'Постановление №482'}
type Transport=ConstructorParameters<typeof ApiClient>[0]
async function open(transport:Transport=async()=>json(page([doc])),props:Record<string,unknown>={},permissions=['documents.view','documents.upload']){
 const wrapper=mount(DocumentPicker,{props:{modelValue:'',mode:'existing',departmentId:'d-4',kinds:['resolution','decision'],kindOptions:[{value:'resolution',label:'Постановление'}],...props,'onUpdate:modelValue':value=>{void wrapper.setProps({modelValue:value})},'onUpdate:mode':value=>{void wrapper.setProps({mode:value})}},global:{plugins:[sessionWith(...permissions)],provide:{[apiKey as symbol]:new ApiClient(transport)}}})
 await flushPromises();return wrapper
}
it('searches by text and allowed kinds without saving or selecting the first result',async()=>{
 const reads:string[]=[],writes:string[]=[]
 const wrapper=await open(async(path,init)=>{(init?.method==='POST'?writes:reads).push(String(path));return json(page([doc]))})
 expect(wrapper.props('modelValue')).toBe('')
 await wrapper.get('[data-document-search]').setValue('  №482  ');await wrapper.get('[data-document-find]').trigger('click');await flushPromises()
 expect(reads.at(-1)).toContain('search=%E2%84%96482');expect(reads.at(-1)).toContain('kind=resolution%2Cdecision')
 await wrapper.get('[data-document-choice]').setValue(doc.id);await flushPromises()
 expect(wrapper.props('modelValue')).toBe('doc-a');expect(wrapper.text()).toContain('Постановление №482')
 expect(wrapper.emitted('selected')?.at(-1)?.[0]).toMatchObject({id:'doc-a'});expect(writes).toEqual([])
})
it('retains a selected document across pages and allows clearing it',async()=>{
 const wrapper=await open(async path=>String(path).includes('page=2')?json({count:26,next:null,previous:'page=1',results:[{...doc,id:'doc-b',title:'Другой документ'}]}):json({count:26,next:'page=2',previous:null,results:[doc]}))
 await wrapper.get('[data-document-choice]').setValue('doc-a');await flushPromises()
 await wrapper.findAll('button').find(button=>button.text()==='Далее')!.trigger('click');await flushPromises()
 expect(wrapper.props('modelValue')).toBe('doc-a');expect(wrapper.get('[data-document-choice]').text()).toContain('Постановление №482')
 await wrapper.get('[data-document-choice]').setValue('');await flushPromises();expect(wrapper.props('modelValue')).toBe('')
})
it('ignores a late search after the query changed',async()=>{
 let resolve!:(value:Response)=>void
 const wrapper=await open(async path=>String(path).includes('search=old')?new Promise(done=>{resolve=done}):json(page([{...doc,id:'doc-b',title:'Новый результат'}])))
 await wrapper.get('[data-document-search]').setValue('old');await wrapper.get('[data-document-find]').trigger('click');await flushPromises()
 await wrapper.get('[data-document-search]').setValue('new');await wrapper.get('[data-document-find]').trigger('click');await flushPromises()
 resolve(json(page([doc])));await flushPromises();expect(wrapper.get('[data-document-choice]').text()).toContain('Новый результат');expect(wrapper.get('[data-document-choice]').text()).not.toContain('Постановление №482')
})
it('creates only when persist is requested and warns before dropping a new document draft',async()=>{
 const writes:string[]=[]
 const wrapper=await open(async(path,init)=>{if(String(path).endsWith('/csrf/'))return json({csrf_token:'t'});if(init?.method==='POST'){writes.push(String(path));return json(doc)}return json(page([]))})
 await wrapper.get('[data-document-new]').trigger('click');await flushPromises();await wrapper.get('[name="document_title"]').setValue('Новое постановление')
 expect(writes).toEqual([]);vi.spyOn(window,'confirm').mockReturnValue(false)
 await wrapper.get('[data-document-existing]').trigger('click');expect(wrapper.props('mode')).toBe('new')
 const prepared=await wrapper.vm.persist();expect(prepared.id).toBe('doc-a');expect(writes).toEqual(['/api/v1/documents/'])
})
it('does not offer upload without upload permission and disables changes while busy',async()=>{
 const wrapper=await open(undefined,{busy:true},['documents.view'])
 expect(wrapper.find('[data-document-new]').exists()).toBe(false)
 expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
})
it('does not offer a document without a required saved file',async()=>{
 const wrapper=await open(undefined,{requireFile:true})
 expect(wrapper.get('option[value="doc-a"]').attributes('disabled')).toBeDefined()
})
it('keeps results when a parent rerenders with an equivalent kinds array',async()=>{
 let reads=0
 const wrapper=await open(async()=>{reads++;return json(page([doc]))})
 expect(reads).toBe(1)
 await wrapper.setProps({kinds:['resolution','decision'],heading:'Уточнённое название поля'});await flushPromises()
 expect(reads).toBe(1)
 expect(wrapper.get('option[value="doc-a"]').text()).toContain('Постановление №482')
})
it('does not replace a new selection with an older detail response',async()=>{
 let finish!:(value:Response)=>void
 const next={...doc,id:'doc-b',title:'Выбранное новое постановление'}
 const wrapper=await open(async path=>String(path).includes('/documents/doc-a/')?new Promise(resolve=>{finish=resolve}):json(page([next])),{modelValue:'doc-a'})
 await wrapper.get('[data-document-choice]').setValue('doc-b');await flushPromises()
 finish(json(doc));await flushPromises()
 expect(wrapper.props('modelValue')).toBe('doc-b')
 expect(wrapper.emitted('selected')?.at(-1)?.[0]).toMatchObject({id:'doc-b'})
 expect(wrapper.text()).toContain('Выбранное новое постановление')
})
it('invalidates pending results when the required kind changes',async()=>{
 let finish!:(value:Response)=>void
 const wrapper=await open(async path=>String(path).includes('kind=resolution')?new Promise(resolve=>{finish=resolve}):json(page([{...doc,id:'result-b',kind:'expert_conclusion',title:'Заключение по работе'}])))
 await wrapper.setProps({kinds:['expert_conclusion']});await flushPromises()
 finish(json(page([doc])));await flushPromises()
 expect(wrapper.get('[data-document-choice]').text()).toContain('Заключение по работе')
 expect(wrapper.find('option[value="doc-a"]').exists()).toBe(false)
 expect(wrapper.props('modelValue')).toBe('')
})
it('retains a new file and the same metadata attempt when upload permission disappears temporarily',async()=>{
 const attempts:{key:string|null;body:string}[]=[]
 const wrapper=await open(async(path,init)=>{
  if(String(path).endsWith('/csrf/'))return json({csrf_token:'t'})
  if(init?.method==='POST'&&String(path).endsWith('/documents/')){
   attempts.push({key:new Headers(init.headers).get('Idempotency-Key'),body:String(init.body)})
   if(attempts.length===1)throw new TypeError('lost metadata reply')
   return json({...doc,source_kind:'uploaded_copy'})
  }
  if(init?.method==='POST')return json({id:'file-1',number:1,original_name:'scan.pdf',content_type:'application/pdf',size:1,sha256:'abc',created_at:'2026-10-29T00:00:00Z',download_url:'/download/',preview_url:'/preview/'})
  return json(page([]))
 })
 await wrapper.get('[data-document-new]').trigger('click');await wrapper.get('[name="document_title"]').setValue('Сохраняемый черновик');await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
 Object.defineProperty(wrapper.get('[name="basis_file"]').element,'files',{value:[new File(['scan'],'scan.pdf')]});await wrapper.get('[name="basis_file"]').trigger('change')
 await expect(wrapper.vm.persist()).rejects.toThrow('lost metadata reply')
 const store=useSessionStore(),rules=store.user!.access['documents.upload']!
 delete store.user!.access['documents.upload'];await flushPromises()
 expect(wrapper.get('[name="document_title"]').element).toHaveProperty('value','Сохраняемый черновик')
 await expect(wrapper.vm.persist()).rejects.toMatchObject({status:403});expect(attempts).toHaveLength(1)
 store.user!.access['documents.upload']=rules;await flushPromises()
 await wrapper.vm.persist();expect(attempts).toHaveLength(2);expect(attempts[1]).toEqual(attempts[0])
})
it('does not reuse cached metadata over an explicitly restricted server link',async()=>{
 const wrapper=await open(undefined,{modelValue:'doc-a',document:doc})
 expect(wrapper.text()).toContain('Постановление №482')
 await wrapper.setProps({document:{id:'doc-a',restricted:true}});await flushPromises()
 expect(wrapper.text()).not.toContain('Постановление №482')
 expect(wrapper.emitted('selected')?.at(-1)?.[0]).toBeNull()
})
