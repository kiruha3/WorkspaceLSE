<script setup lang="ts">
import {computed,onBeforeUnmount,ref} from 'vue'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import type {BasisDocument,DocumentKind,Page} from '../../api/types'
import {documentPath,type WorkDocumentResponse} from '../../api/workDocuments'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const props=defineProps<{workId:string;expectedVersion:number;departmentId:string;kindOptions:{code:DocumentKind;name:string}[];authorized:boolean;allowCreate:boolean;initialFile?:File;embedded?:boolean;complex?:boolean;allowComplex?:boolean}>()
const emit=defineEmits<{saved:[value:WorkDocumentResponse];changed:[];refresh:[]}>()
const api=useApi(),requests=new LatestRequest()
const mode=ref(props.allowCreate?'new':'existing'),search=ref(''),options=ref<Page<BasisDocument>|null>(null),pickerPage=ref(1),pickerBusy=ref(false)
const selected=ref<BasisDocument|null>(null),note=ref(''),reason=ref(''),basis=ref<InstanceType<typeof BasisDocumentForm>|null>(null)
const shareComplex=ref(false)
const department=props.departmentId
const kindOptions=computed(()=>[...props.kindOptions].sort((a,b)=>Number(b.code==='case_material')-Number(a.code==='case_material')).map(item=>({value:item.code,label:item.name})))
const busy=ref(false),error=ref<unknown>(null),workConflict=ref(false),done=ref(false),uncertain=ref(false)
const preparation=ref<{version:number;reason:string;note:string;mode:string;selected:BasisDocument|null;shareComplex:boolean}|null>(null)
const attempt=ref<{key:string;body:Record<string,unknown>}|null>(null)
const frozen=computed(()=>Boolean(preparation.value)),dirty=computed(()=>!done.value&&Boolean(preparation.value||basis.value?.dirty||selected.value||note.value||reason.value||shareComplex.value))
function selectMode(next:string){
  if(mode.value===next)return true
  if((mode.value==='new'?basis.value?.dirty:Boolean(selected.value))&&!window.confirm('В текущем способе есть несохранённый документ. Переключить способ добавления?'))return false
  mode.value=next;return true
}
async function loadOptions(page=1){
  if(!selectMode('existing'))return
  pickerBusy.value=true;error.value=null;pickerPage.value=page
  try{await requests.run(signal=>api.request<Page<BasisDocument>>(documentPath(props.workId)+`options/?search=${encodeURIComponent(search.value.trim())}&page=${page}`,{signal}),value=>{options.value=value;pickerBusy.value=false})}
  catch(cause){error.value=cause;pickerBusy.value=false}
}
function acceptVersion(version=props.expectedVersion){
  if(!workConflict.value||!preparation.value)return
  preparation.value={...preparation.value,version}
  if(attempt.value)attempt.value={key:newCommandKey(),body:{...attempt.value.body,expected_version:version}}
  workConflict.value=false;error.value=null;emit('changed')
}
function editAgain(){if(uncertain.value)return;preparation.value=null;attempt.value=null;workConflict.value=false;error.value=null;emit('changed')}
async function persist(version=props.expectedVersion,reasonOverride?:string):Promise<WorkDocumentResponse|null>{
  if(busy.value||done.value||workConflict.value||!props.authorized)return null
  const chosenReason=reasonOverride??reason.value.trim()
  if(!preparation.value&&!chosenReason){error.value=new ApiError(400,'validation_error','Укажите причину добавления документа.');return null}
  // Capture the work version BEFORE the first metadata/upload request. GETs
  // and new props may refresh context, never this accepted attempt packet.
  if(!preparation.value)preparation.value={version,reason:chosenReason,note:note.value.trim(),mode:mode.value,selected:selected.value,shareComplex:shareComplex.value&&Boolean(props.allowComplex)}
  busy.value=true;error.value=null
  try{
    if(!attempt.value){
      const prepared=preparation.value
      const document=prepared.mode==='existing'?prepared.selected:await basis.value!.persist()
      if(!document)throw new ApiError(400,'validation_error','Выберите существующий документ.')
      attempt.value={key:newCommandKey(),body:{expected_version:prepared.version,document_id:document.id,note:prepared.note,reason:prepared.reason,...(prepared.shareComplex?{share_with_complex:true}:{})}}
    }
    const value=await api.request<WorkDocumentResponse>(documentPath(props.workId),{method:'POST',body:attempt.value.body,headers:{'Idempotency-Key':attempt.value.key}})
    done.value=true;emit('saved',value);emit('changed');return value
  }catch(cause){
    error.value=cause
    uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'
    workConflict.value=cause instanceof ApiError&&cause.status===409&&cause.code==='version_conflict'&&Boolean(attempt.value)
    return null
  }finally{busy.value=false}
}
onBeforeUnmount(()=>requests.cancel())
defineExpose({persist,dirty,busy,workConflict,acceptVersion})
</script>
<template>
  <form data-archive-source-form class="form-grid" @submit.prevent="persist()">
    <template v-if="!embedded"><h3>Добавить документ в архив</h3><div class="button-row"><button v-if="allowCreate" type="button" :disabled="busy||frozen" @click="selectMode('new')">Новый документ</button><button data-source-existing type="button" :disabled="busy||frozen" @click="loadOptions()">Выбрать существующий</button></div></template>
    <BasisDocumentForm v-if="mode==='new'" ref="basis" :department-id="department" :kind-options="kindOptions" :initial-file="initialFile" :allow-external-source="true" :busy="busy||!authorized" :input-locked="frozen" heading="Документ архива" saved-note="Связь с экспертизой сохраняется отдельным шагом; подтверждённые итоги не изменяются." @changed="emit('changed')"/>
    <section v-else class="form-grid"><div class="form-columns"><label>Поиск среди доступных документов<input v-model="search" name="existing_search" :disabled="busy||frozen"/></label><button type="button" :disabled="pickerBusy||busy||frozen" @click="loadOptions()">Найти документ</button></div><p v-if="pickerBusy" role="status">Поиск документов…</p><div v-if="options" class="archive-picker"><button v-for="item in options.results" :key="item.id" type="button" :data-use-existing="item.id" :disabled="busy||frozen" @click="selected=item;emit('changed')">{{item.title}}</button><p v-if="!options.results.length" class="muted">Доступных документов по этому запросу нет.</p><div class="button-row"><button v-if="options.previous" type="button" :disabled="busy||frozen" @click="loadOptions(pickerPage-1)">Назад</button><button v-if="options.next" type="button" :disabled="busy||frozen" @click="loadOptions(pickerPage+1)">Дальше</button></div></div><BasisPreview v-if="selected" :document="selected" heading="Выбранный документ"/></section>
    <fieldset v-if="!embedded" class="form-grid" :disabled="busy||frozen||!authorized"><label>Примечание к связи<textarea v-model="note" name="archive_note" @input="emit('changed')"/></label><label>Причина добавления<textarea v-model="reason" name="archive_reason" required @input="emit('changed')"/></label></fieldset>
    <label v-if="complex&&!embedded" class="check-label"><input v-model="shareComplex" name="share_with_complex" type="checkbox" :disabled="busy||frozen||!allowComplex" @change="emit('changed')" />Прикрепить ко всем номерам комплекса</label><p v-if="complex&&!embedded&&!allowComplex" class="muted compact">Для общего прикрепления нужно право связывать документы с каждой экспертизой комплекса.</p>
    <ApiMessage :error="error"/>
    <section v-if="workConflict&&!embedded" class="message"><p>Работа изменилась. Документ и выбранный файл сохранены в форме. Обновите архив и явно примите актуальную версию работы.</p><div class="button-row"><button type="button" :disabled="busy" @click="emit('refresh')">Обновить сведения работы</button><button data-accept-work-version type="button" :disabled="busy" @click="acceptVersion()">Принять версию {{expectedVersion}} работы</button></div></section>
    <p v-if="done" class="message message-success" role="status">Документ связан с экспертизой.</p>
    <div v-if="!done" class="button-row"><button v-if="!embedded" class="button-primary" type="submit" :disabled="busy||workConflict||!authorized">{{busy?'Сохранение…':frozen?'Повторить ту же попытку':'Сохранить документ и связь'}}</button><button v-if="frozen&&!busy&&!uncertain" type="button" @click="editAgain">Изменить ввод для новой попытки</button></div>
  </form>
</template>
