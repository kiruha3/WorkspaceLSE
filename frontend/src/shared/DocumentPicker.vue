<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {ApiError,LatestRequest,useApi} from '../api/client'
import type {BasisDocument,DocumentKind,DocumentLink,Page} from '../api/types'
import {useSessionStore} from '../stores/session'
import BasisDocumentForm from './BasisDocumentForm.vue'
import BasisPreview from './BasisPreview.vue'
import ApiMessage from './ui/ApiMessage.vue'
import PaginationBar from './ui/PaginationBar.vue'

const props=withDefaults(defineProps<{modelValue:string;mode:string;departmentId:string;document?:DocumentLink;heading?:string;name?:string;kinds?:DocumentKind[];kindOptions?:{value:DocumentKind;label:string}[];requireFile?:boolean;required?:boolean;busy?:boolean;inputLocked?:boolean;savedNote?:string}>(),{name:'document_id',kinds:()=>[]})
const emit=defineEmits<{'update:modelValue':[string];'update:mode':[string];selected:[BasisDocument|null];changed:[]}>()
const api=useApi(),session=useSessionStore(),requests=new LatestRequest(),details=new LatestRequest()
const search=ref(''),loading=ref(false),error=ref<unknown>(null),currentPage=ref(1)
const list=ref<Page<BasisDocument>>({count:0,next:null,previous:null,results:[]}),selected=ref<BasisDocument|null>(null)
const form=ref<InstanceType<typeof BasisDocumentForm>|null>(null),cache=new Map<string,BasisDocument>()
const initialId=props.modelValue,initialMode=props.mode
const canRead=computed(()=>session.can('documents.view')),canCreate=computed(()=>session.can('documents.upload'))
const locked=computed(()=>Boolean(props.busy||props.inputLocked))
const allowed=(doc:BasisDocument)=>!props.kinds.length||props.kinds.includes(doc.kind)
const usable=(doc:BasisDocument)=>allowed(doc)&&(!props.requireFile||Boolean(doc.versions.length))
const options=computed(()=>canRead.value?list.value.results.filter(doc=>allowed(doc)&&!(props.document&&'restricted' in props.document&&props.document.id===doc.id)):[])
const dirty=computed(()=>props.modelValue!==initialId||props.mode!==initialMode||Boolean(form.value?.dirty))
const uploadConflict=computed(()=>Boolean(form.value?.uploadConflict))
const key=computed(()=>(props.kindOptions??[]).map(item=>item.value).join(','))
function show(doc:BasisDocument){return `${doc.title||'Без названия'} · ${doc.versions.length?doc.versions.at(-1)!.original_name:doc.source_kind==='paper_original'?'Бумажный оригинал':'Без сохранённого файла'}`}
function notify(doc:BasisDocument|null){selected.value=doc;emit('selected',doc)}
async function hydrate(){
 details.cancel();selected.value=null
 if(!props.modelValue)return emit('selected',null)
 const id=props.modelValue
 if(!canRead.value||(props.document&&'restricted' in props.document&&props.document.id===id)){cache.delete(id);notify(null);return}
 const given=props.document&&!('restricted' in props.document)&&props.document.id===id?props.document:null
 const known=given??cache.get(id)
 if(known&&usable(known)){cache.set(id,known);notify(known);return}
 if(props.mode==='new')return
 try{await details.run(signal=>api.request<BasisDocument>(`/documents/${encodeURIComponent(id)}/`,{signal}),doc=>{
  if(props.modelValue!==id||doc.id!==id)return
  if(!usable(doc))throw new ApiError(400,'document_invalid','Выберите документ нужного вида с требуемым файлом.')
  cache.set(id,doc);notify(doc)
 })}catch(cause){error.value=cause}
}
async function load(page=1){
 if(locked.value||!canRead.value||props.mode!=='existing')return
 loading.value=true;error.value=null
 const query=new URLSearchParams({search:search.value.trim(),page:String(page)})
 if(props.kinds.length)query.set('kind',props.kinds.join(','))
 try{await requests.run(signal=>api.request<Page<BasisDocument>>(`/documents/?${query}`,{signal}),value=>{
  if(!Array.isArray(value.results))throw new ApiError(502,'invalid_response','Не удалось прочитать список документов.')
  list.value=value;currentPage.value=page
  for(const doc of value.results.filter(allowed))cache.set(doc.id,doc)
  loading.value=false
 })}catch(cause){error.value=cause;loading.value=false}
}
function choose(event:Event){
 if(locked.value)return
 const id=(event.target as HTMLSelectElement).value,doc=id?cache.get(id)??null:null
 if(id&&(!doc||!usable(doc)))return
 details.cancel();selected.value=doc;emit('update:modelValue',id);emit('selected',doc);emit('changed')
}
function changeMode(mode:string){
 if(locked.value||mode===props.mode||mode==='new'&&!canCreate.value)return
 if(props.mode==='new'&&form.value?.dirty&&!window.confirm('Есть несохранённый новый документ. Перейти к выбору существующего?'))return
 requests.cancel();loading.value=false;error.value=null;emit('update:mode',mode);emit('changed')
}
async function persist():Promise<BasisDocument>{
 if(props.mode==='new'){
  if(!canCreate.value||!form.value)throw new ApiError(403,'forbidden','Добавление нового документа недоступно.')
  return form.value.persist()
 }
 if(!canRead.value)throw new ApiError(403,'forbidden','Просмотр сохранённого документа недоступен.')
 if(!selected.value||selected.value.id!==props.modelValue||!usable(selected.value))throw new ApiError(400,'document_required','Выберите сохранённый документ.')
 return selected.value
}
watch([()=>props.modelValue,()=>props.document,()=>props.kinds.join(','),()=>props.requireFile,canRead],()=>{void hydrate()},{immediate:true})
watch([()=>props.mode,()=>props.kinds.join(','),canRead],()=>{requests.cancel();list.value={count:0,next:null,previous:null,results:[]};loading.value=false;if(props.mode==='existing')void load()},{immediate:true})
onBeforeUnmount(()=>{requests.cancel();details.cancel()})
defineExpose({persist,dirty,uploadConflict})
</script>

<template>
 <fieldset class="document-picker form-grid" :disabled="locked" data-document-picker>
  <legend>{{heading||'Документ'}}</legend>
  <div class="document-actions"><button v-if="mode==='new'" data-document-existing type="button" @click="changeMode('existing')">Выбрать сохранённый</button><template v-else><label class="grow">Поиск по названию или имени файла<input v-model="search" data-document-search type="search" maxlength="500" :disabled="!canRead" @keydown.enter.prevent="load()"/></label><button data-document-find type="button" :disabled="!canRead" @click="load()">Найти</button></template><button v-if="canCreate&&mode!=='new'" data-document-new type="button" @click="changeMode('new')">+ Добавить новый</button></div>
  <template v-if="mode==='existing'">
   <ApiMessage :error="error"/><p v-if="loading" role="status" class="muted">Поиск документов…</p><p v-if="!canRead" class="muted">Для выбора сохранённого документа требуется право просмотра документов.</p>
   <label>Сохранённый документ<select :value="modelValue" :name="name" data-document-choice :required="required" :disabled="!canRead" @change="choose"><option value="">{{required?'Выберите документ':'Не выбран'}}</option><option v-if="modelValue&&!options.some(doc=>doc.id===modelValue)" :value="modelValue">{{selected?show(selected):'Ранее выбранный документ'}}</option><option v-for="doc in options" :key="doc.id" :value="doc.id" :disabled="!usable(doc)">{{show(doc)}}{{!usable(doc)?' · Нужен сохранённый файл':''}}</option></select></label>
   <p v-if="!loading&&!error&&canRead&&!list.count" class="muted">Документы не найдены. Измените поиск{{canCreate?' или добавьте новый документ.':'.'}}</p>
   <PaginationBar v-if="list.next||list.previous" :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="locked||loading" @change="load"/>
   <BasisPreview v-if="selected" :document="selected" heading="Выбранный документ"/>
  </template>
  <BasisDocumentForm v-else :key="key" ref="form" :department-id="departmentId" :kind-options="kindOptions" :require-file="requireFile" :busy="busy" :input-locked="inputLocked||!canCreate" :heading="heading||'Новый документ'" :saved-note="savedNote" @changed="emit('changed')"/>
  <p v-if="mode==='new'&&!canCreate" class="muted">Добавление нового документа больше не разрешено. Черновик и выбранный файл сохранены в форме.</p>
 </fieldset>
</template>

<style scoped>
.document-picker{min-width:0;margin:0;padding:16px;border:1px solid var(--border);border-radius:10px}
.document-picker legend{font-weight:600;padding:0 6px}.document-actions{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.grow{flex:1;min-width:180px}.document-actions button{flex-shrink:0}.document-picker select{max-width:100%}
</style>
