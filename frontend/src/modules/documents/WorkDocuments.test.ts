import {afterEach,expect,it,vi} from 'vitest'
import {enableAutoUnmount,flushPromises,mount} from '@vue/test-utils'
import {createMemoryHistory,createRouter,RouterView} from 'vue-router'
import {ApiClient,apiKey} from '../../api/client'
import {json,sessionWith} from '../../test/fixtures'
import {basis,department} from '../../test/intakeFixtures'
import type {DocumentKind} from '../../api/types'
import {hasDirtyForms} from '../../shared/ui/useDirtyGuard'
import WorkDocumentsPage from './WorkDocumentsPage.vue'
import DocumentSourceForm from './DocumentSourceForm.vue'
import DocumentBatchUpload from './DocumentBatchUpload.vue'
import DocumentVersionUpload from './DocumentVersionUpload.vue'
import {router as applicationRouter} from '../../router'
import {useSessionStore} from '../../stores/session'

const v1={id:'f1',number:1,original_name:'first.pdf',relative_path:'',content_type:'application/pdf',size:4,sha256:'sha1',created_at:'2026-10-28',download_url:'/file1/download/',preview_url:'/file1/preview/'}
const v2={...v1,id:'f2',number:2,original_name:'second.pdf',preview_url:'/file2/preview/'}
const doc={...basis,id:'doc1',title:'Заключение №1',source_url:'',versions:[v1,v2]}
const context={id:'work1',registration_number:'1/3-1-26',version:3,state:'completed',material:{id:'material1'},department}
const kinds:{code:DocumentKind;name:string}[]=[{code:'case_material',name:'Материалы дела / иные документы'},{code:'decision',name:'Определение'}]
const library={count:1,next:null,previous:null,context,can_link:true,can_unlink:true,can_create:true,document_kinds:kinds,detached_links:[],results:[{document:doc,origins:[{kind:'closure',id:'closure1',label:'Принятое окончание',accepted_version_id:'f1'}],extra_links:[]}]}
const sourceProps={workId:'work1',expectedVersion:3,departmentId:department.id,kindOptions:kinds,authorized:true,allowCreate:true}
type Transport=ConstructorParameters<typeof ApiClient>[0]
const globals=(client:ApiClient)=>({provide:{[apiKey as symbol]:client}})
afterEach(()=>vi.restoreAllMocks());enableAutoUnmount(afterEach)
async function open(value:unknown=library,transport?:Transport){
  const pinia=sessionWith('expertise.view','documents.view','documents.link','documents.unlink','documents.upload')
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/expertises/:id/documents',component:WorkDocumentsPage},{path:'/expertises/:id',component:{template:'<p>Карточка</p>'}},{path:'/workspace',component:{template:'<p>Рабочее место</p>'}}]})
  await router.push('/expertises/work1/documents?return=%2Fexpertises%2Fwork1%3Freturn%3D%252Fexpertises%253Fpage%253D2')
  const client=new ApiClient(transport??(async()=>json(value)))
  const wrapper=mount(RouterView,{global:{plugins:[pinia,router],...globals(client)}});await flushPromises()
  return {wrapper,router}
}
async function files(wrapper:ReturnType<typeof mount>,selector:string,values:File[]){
  const input=wrapper.get(selector);Object.defineProperty(input.element,'files',{value:values,configurable:true});await input.trigger('change');await flushPromises()
}
it('shows unified provenance and pins acceptedV1 instead of the latest upload',async()=>{
  const {wrapper}=await open()
  expect(wrapper.text()).toContain('1/3-1-26')
  expect(wrapper.text()).toContain('Принятое окончание')
  expect(wrapper.get('iframe').attributes('src')).toBe('/file1/preview/')
  expect(wrapper.get('[data-archive-back]').attributes('href')).toContain('/expertises/work1?return=')
})
it('keeps an explicitly unknown accepted version blank even with V2 present',async()=>{
  const {wrapper}=await open({...library,results:[{...library.results[0],origins:[{kind:'closure',id:'unknown',label:'Бумажное окончание',accepted_version_id:null}]}]})
  expect(wrapper.find('iframe').exists()).toBe(false)
  expect(wrapper.text()).toContain('Подтверждённая версия файла не установлена')
})
it('renders a read-only archive and does not offer unsupported mutations',async()=>{
  const {wrapper}=await open({...library,can_link:false,can_unlink:false,can_create:false})
  expect(wrapper.find('[data-open-document-source]').exists()).toBe(false)
  expect(wrapper.text()).toContain('Только просмотр')
})
it('sends search and kind to the server and keeps loading errors recoverable',async()=>{
  const paths:string[]=[]
  const {wrapper}=await open(library,async(input)=>{paths.push(String(input));return json(library)})
  await wrapper.get('[name="archive_search"]').setValue('Письмо суда')
  await wrapper.get('[name="archive_kind"]').setValue('case_material')
  await wrapper.get('[data-archive-filters]').trigger('submit');await flushPromises()
  expect(paths.at(-1)).toContain('search=')
  expect(paths.at(-1)).toContain('kind=case_material')
})
it('links an existing document without creating metadata or uploading a duplicate',async()=>{
  const posts:{path:string;body:Record<string,unknown>}[]=[]
  const client=new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.method==='POST'){posts.push({path,body:JSON.parse(String(init.body))});return json({event:{id:'linked'},library})}
    return json({count:1,next:null,previous:null,results:[doc]})
  })
  const wrapper=mount(DocumentSourceForm,{props:sourceProps,global:globals(client)})
  await wrapper.get('[data-source-existing]').trigger('click');await flushPromises()
  await wrapper.get('[data-use-existing="doc1"]').trigger('click')
  await wrapper.get('[name="archive_reason"]').setValue('Общее приложение')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(posts).toHaveLength(1)
  expect(posts[0]?.path).toBe('/api/v1/expertises/work1/documents/')
  expect(posts[0]?.body).toMatchObject({expected_version:3,document_id:'doc1',reason:'Общее приложение'})
})
it('recovers lost link response using the same packet after a late GET/prop version update',async()=>{
  const attempts:{key:string|null;body:string}[]=[];let creates=0
  const client=new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(path.endsWith('/documents/')&&!path.includes('/expertises/')){creates++;return json({...doc,versions:[]},201)}
    attempts.push({key:new Headers(init?.headers).get('Idempotency-Key'),body:String(init?.body)})
    if(attempts.length===1)throw new TypeError('Ответ потерян после сохранения')
    return json({event:{id:'one'},library})
  })
  const wrapper=mount(DocumentSourceForm,{props:sourceProps,global:globals(client)})
  await wrapper.get('[name="document_title"]').setValue('Дополнение')
  await wrapper.get('[name="archive_reason"]').setValue('Дослано')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  await wrapper.setProps({expectedVersion:99})
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(creates).toBe(1);expect(attempts[1]).toEqual(attempts[0])
  expect(JSON.parse(attempts[1]!.body).expected_version).toBe(3)
})
it('retains input on403 and requires explicit adoption after a work409',async()=>{
  let failure=403;const bodies:Record<string,unknown>[]=[]
  const client=new ApiClient(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'token'})
    if(String(input).endsWith('/documents/')&&!String(input).includes('/expertises/'))return json({...doc,versions:[]},201)
    bodies.push(JSON.parse(String(init?.body)))
    return failure?json({code:'version_conflict',message:'Сверьте права или версию',field_errors:{}},failure):json({event:{id:'linked'},library})
  })
  const wrapper=mount(DocumentSourceForm,{props:sourceProps,global:globals(client)})
  await wrapper.get('[name="document_title"]').setValue('Не терять')
  await wrapper.get('[name="archive_reason"]').setValue('Дослано')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Не терять')
  failure=409;await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  await wrapper.setProps({expectedVersion:7})
  expect(wrapper.get('[data-accept-work-version]').text()).toContain('7')
  await wrapper.get('[data-accept-work-version]').trigger('click')
  failure=0;await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(bodies.at(-1)?.expected_version).toBe(7)
})
it('captures the work version before awaiting metadata and upload',async()=>{
  let resolve!: (value:Response)=>void;const bodies:Record<string,unknown>[]=[]
  const client=new ApiClient(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'token'})
    if(String(input).endsWith('/documents/')&&!String(input).includes('/expertises/'))return new Promise<Response>(done=>{resolve=done})
    bodies.push(JSON.parse(String(init?.body)));return json({event:{id:'linked'},library})
  })
  const wrapper=mount(DocumentSourceForm,{props:sourceProps,global:globals(client)})
  await wrapper.get('[name="document_title"]').setValue('Архив')
  await wrapper.get('[name="archive_reason"]').setValue('По описи')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  await wrapper.setProps({expectedVersion:12})
  resolve(json({...doc,versions:[]},201));await flushPromises()
  expect(bodies[0]?.expected_version).toBe(3)
})
it('uploads a folder sequentially, retains partial failures and skips confirmed successes on retry',async()=>{
  const creates:string[]=[],uploads:string[]=[],links:Record<string,unknown>[]=[];let failed=false
  const client=new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(path.endsWith('/documents/')&&!path.includes('/expertises/')){const body=JSON.parse(String(init?.body));creates.push(body.title);return json({...doc,id:body.title,version:1,versions:[]},201)}
    if(init?.body instanceof FormData){uploads.push(String(init.body.get('relative_path')));return json({...v1,id:'file-'+uploads.length},201)}
    const body=JSON.parse(String(init?.body));links.push(body)
    if(body.document_id==='two.pdf'&&!failed){failed=true;throw new TypeError('Ответ потерян')}
    return json({event:{id:'linked'},library:{...library,context:{...context,version:Number(body.expected_version)+1}}})
  })
  const wrapper=mount(DocumentBatchUpload,{props:{...sourceProps},global:globals(client)})
  const selected=['one.pdf','two.pdf'].map(name=>{const file=new File(['scan'],name);Object.defineProperty(file,'webkitRelativePath',{value:'Дело/'+name});return file})
  await files(wrapper,'[data-folder-files]',selected)
  await wrapper.get('[name="batch_reason"]').setValue('Выбранная опись')
  await wrapper.get('[data-run-batch]').trigger('click');await flushPromises()
  expect(creates).toEqual(['one.pdf','two.pdf']);expect(uploads).toEqual(['Дело/one.pdf','Дело/two.pdf'])
  expect(wrapper.text()).toContain('1 из 2')
  await wrapper.get('[data-run-batch]').trigger('click');await flushPromises()
  expect(creates).toHaveLength(2);expect(uploads).toHaveLength(2)
  expect(links.map(body=>body.expected_version)).toEqual([3,4,4])
  expect(wrapper.text()).toContain('2 из 2')
})
it('rejects more than100 selected files without starting writes',async()=>{
  let writes=0;const wrapper=mount(DocumentBatchUpload,{props:sourceProps,global:globals(new ApiClient(async()=>{writes++;return json(library)}))})
  await files(wrapper,'[data-folder-files]',Array.from({length:101},(_,i)=>new File(['x'],`${i}.pdf`)))
  expect(wrapper.text()).toContain('100');expect(writes).toBe(0)
})
it('keeps an unsaved page form behind the navigation dirty guard',async()=>{
  const {wrapper,router}=await open()
  await wrapper.get('[data-open-document-source]').trigger('click')
  await wrapper.get('[name="document_title"]').setValue('Не терять при выходе')
  expect(hasDirtyForms()).toBe(true)
  vi.spyOn(window,'confirm').mockReturnValue(false)
  await router.push('/workspace')
  expect(router.currentRoute.value.path).toBe('/expertises/work1/documents')
})
it('preserves the chosen version file on409 until the current document version is explicitly accepted',async()=>{
  const versions:string[]=[];let conflict=true
  const client=new ApiClient(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.body instanceof FormData){versions.push(String(init.body.get('expected_version')));return conflict?json({code:'version_conflict',message:'Документ изменён',field_errors:{}},409):json({...v2,id:'file-new'},201)}
    return json({...doc,version:9})
  })
  const wrapper=mount(DocumentVersionUpload,{props:{document:doc,authorized:true},global:globals(client)})
  await files(wrapper,'[data-version-file]',[new File(['new'],'new.pdf')])
  await wrapper.get('[data-version-upload]').trigger('submit');await flushPromises()
  await wrapper.get('[data-refresh-file-version]').trigger('click');await flushPromises()
  await wrapper.get('[data-accept-file-version]').trigger('click');conflict=false
  await wrapper.get('[data-version-upload]').trigger('submit');await flushPromises()
  expect(versions).toEqual([String(doc.version),'9'])
})

it('keeps document-upload conflict recovery available inside a frozen source attempt',async()=>{
  let uploadConflict=true
  const client=new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.body instanceof FormData)return uploadConflict?json({code:'version_conflict',message:'Документ изменён',field_errors:{}},409):json(v1,201)
    if(path.endsWith('/documents/doc1/'))return json({...doc,version:8,versions:[]})
    if(path.includes('/expertises/'))return json({event:{id:'linked'},library})
    return json({...doc,version:1,versions:[]},201)
  })
  const wrapper=mount(DocumentSourceForm,{props:{...sourceProps,initialFile:new File(['x'],'scan.pdf')},global:globals(client)})
  await wrapper.get('[name="archive_reason"]').setValue('Сохранить копию')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(wrapper.get('[data-refresh-document-version]').attributes('disabled')).toBeUndefined()
  await wrapper.get('[data-refresh-document-version]').trigger('click');await flushPromises()
  await wrapper.get('[data-accept-document-version]').trigger('click');uploadConflict=false
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(wrapper.emitted('saved')).toHaveLength(1)
})

it('requires explicit batch version adoption after409 and keeps files after403',async()=>{
  let failure=403,creates=0,uploads=0;const bodies:Record<string,unknown>[]=[]
  const client=new ApiClient(async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.body instanceof FormData){uploads++;return json(v1,201)}
    if(!path.includes('/expertises/')){creates++;return json({...doc,version:1,versions:[]},201)}
    const body=JSON.parse(String(init?.body));bodies.push(body)
    return failure?json({code:'version_conflict',message:'Сверьте версию или права',field_errors:{}},failure):json({event:{id:'linked'},library:{...library,context:{...context,version:8}}})
  })
  const wrapper=mount(DocumentBatchUpload,{props:sourceProps,global:globals(client)})
  await files(wrapper,'[data-folder-files]',[new File(['x'],'case.pdf')])
  await wrapper.get('[name="batch_reason"]').setValue('Пакетная загрузка')
  await wrapper.get('[data-run-batch]').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('case.pdf')
  failure=409;await wrapper.get('[data-run-batch]').trigger('click');await flushPromises()
  await wrapper.setProps({expectedVersion:7})
  expect(wrapper.get('[data-run-batch]').attributes('disabled')).toBeDefined()
  await wrapper.get('[data-accept-batch-version]').trigger('click')
  failure=0;await wrapper.get('[data-run-batch]').trigger('click');await flushPromises()
  expect(creates).toBe(1);expect(uploads).toBe(1)
  expect(bodies.map(body=>body.expected_version)).toEqual([3,3,7])
})

it('resets a general preview to the accepted context when another document is selected',async()=>{
  const second={...library.results[0]!,document:{...doc,id:'doc2',title:'Другое заключение'},origins:[{kind:'closure',id:'closure2',label:'Без принятого файла',accepted_version_id:null}]}
  const {wrapper}=await open({...library,count:2,results:[library.results[0],second]})
  await wrapper.get('[name="archive_origin"]').setValue('latest')
  expect(wrapper.get('iframe').attributes('src')).toBe('/file2/preview/')
  await wrapper.findAll('.archive-document')[1]!.trigger('click')
  expect(wrapper.find('iframe').exists()).toBe(false)
  expect(wrapper.text()).toContain('Подтверждённая версия файла не установлена')
})

it('does not discard a selected scan when switching the source workflow is cancelled',async()=>{
  const wrapper=mount(DocumentSourceForm,{props:sourceProps,global:globals(new ApiClient(async()=>json(library)))})
  await wrapper.get('[name="document_title"]').setValue('Новая копия')
  await wrapper.get('[name="source_kind"]').setValue('uploaded_copy')
  await files(wrapper,'input[type="file"]',[new File(['scan'],'keep.pdf')])
  vi.spyOn(window,'confirm').mockReturnValue(false)
  await wrapper.get('[data-source-existing]').trigger('click');await flushPromises()
  expect(wrapper.find('[name="document_title"]').exists()).toBe(true)
  expect((wrapper.get('[name="document_title"]').element as HTMLInputElement).value).toBe('Новая копия')
})

it('retains an unsaved version file if a later archive GET no longer lists its document',async()=>{
  let missing=false
  const {wrapper}=await open(library,async()=>json(missing?{...library,count:0,results:[]}:library))
  await files(wrapper,'[data-version-file]',[new File(['new'],'unsaved.pdf')])
  missing=true
  const refresh=wrapper.findAll('button').find(button=>button.text()==='Обновить архив')!
  await refresh.trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('unsaved.pdf')
  expect(hasDirtyForms()).toBe(true)
})

it('requires both the backend archive capability and read permissions at the application route',async()=>{
  sessionWith('expertise.view','documents.view')
  await applicationRouter.push('/expertises/work1/documents')
  expect(applicationRouter.currentRoute.value.path).toBe('/workspace')
  useSessionStore().user!.supported_modules=['work_documents']
  await applicationRouter.push('/expertises/work1/documents')
  expect(applicationRouter.currentRoute.value.path).toBe('/expertises/work1/documents')
})

it('retries a lost version-upload response with its original version and key after a GET update',async()=>{
  const attempts:{version:string;key:string|null}[]=[]
  const client=new ApiClient(async(input,init)=>{
    if(String(input).endsWith('/csrf/'))return json({csrf_token:'token'})
    const body=init!.body as FormData;attempts.push({version:String(body.get('expected_version')),key:new Headers(init?.headers).get('Idempotency-Key')})
    if(attempts.length===1)throw new TypeError('Ответ после загрузки потерян')
    return json(v2,201)
  })
  const wrapper=mount(DocumentVersionUpload,{props:{document:doc,authorized:true},global:globals(client)})
  await files(wrapper,'[data-version-file]',[new File(['new'],'new.pdf')])
  await wrapper.get('[data-version-upload]').trigger('submit');await flushPromises()
  await wrapper.setProps({document:{...doc,version:99}})
  await wrapper.get('[data-version-upload]').trigger('submit');await flushPromises()
  expect(attempts[1]).toEqual(attempts[0]);expect(attempts[0]?.key).toBeTruthy()
  expect(wrapper.emitted('saved')).toHaveLength(1)
})

it('allows explicit replacement of a rejected version file instead of locking an unfixable400 attempt',async()=>{
  const client=new ApiClient(async(input)=>String(input).endsWith('/csrf/')?json({csrf_token:'token'}):json({code:'validation_error',message:'Файл превышает предел',field_errors:{}},400))
  const wrapper=mount(DocumentVersionUpload,{props:{document:doc,authorized:true},global:globals(client)})
  await files(wrapper,'[data-version-file]',[new File(['large'],'large.pdf')])
  await wrapper.get('[data-version-upload]').trigger('submit');await flushPromises()
  expect(wrapper.text()).toContain('large.pdf')
  await wrapper.get('[data-reset-version-file]').trigger('click')
  expect(wrapper.get('[data-version-file]').attributes('disabled')).toBeUndefined()
})

it('opens accessible detached-history documents but never exposes a restricted history file',async()=>{
  const history=[{id:'old-link',document:doc,note:'',created_at:'2026-10-01',detached_at:'2026-10-28',detach_reason:'Снята только связь'},
    {id:'closed-link',document:{id:'secret',restricted:true},note:'',created_at:'2026-10-01',detached_at:'2026-10-28',detach_reason:'Снято'}]
  const {wrapper}=await open({...library,detached_links:history})
  expect(wrapper.find('[data-history-preview="closed-link"]').exists()).toBe(false)
  await wrapper.get('[data-history-preview="old-link"]').trigger('click')
  expect(wrapper.findAll('iframe').at(-1)?.attributes('src')).toBe('/file2/preview/')
})

it('reapplies the visible filter after a successful link instead of displaying an unfiltered count',async()=>{
  const reads:string[]=[]
  const {wrapper}=await open(library,async(input,init)=>{
    const path=String(input)
    if(path.endsWith('/csrf/'))return json({csrf_token:'token'})
    if(init?.method==='POST')return path.includes('/expertises/')?json({event:{id:'linked'},library:{...library,count:2}}):json({...doc,versions:[]},201)
    reads.push(path);return json(library)
  })
  await wrapper.get('[name="archive_search"]').setValue('Заключение')
  await wrapper.get('[data-archive-filters]').trigger('submit');await flushPromises()
  const before=reads.length
  await wrapper.get('[data-open-document-source]').trigger('click')
  await wrapper.get('[name="document_title"]').setValue('Заключение новое')
  await wrapper.get('[name="archive_reason"]').setValue('Дослано')
  await wrapper.get('[data-archive-source-form]').trigger('submit');await flushPromises()
  expect(reads.length).toBeGreaterThan(before)
  expect(decodeURIComponent(reads.at(-1)!)).toContain('search=Заключение')
})
