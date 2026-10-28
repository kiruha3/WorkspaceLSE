<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {RouterLink,useRoute,useRouter} from 'vue-router'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import type {BasisDocument} from '../../api/types'
import {documentPath,originKey,type WorkDocumentLibrary,type WorkDocumentResponse,type WorkDocumentEntry} from '../../api/workDocuments'
import {useSessionStore} from '../../stores/session'
import {useDirtyGuard} from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import DocumentSourceForm from './DocumentSourceForm.vue'
import DocumentBatchUpload from './DocumentBatchUpload.vue'
import DocumentVersionUpload from './DocumentVersionUpload.vue'

const api=useApi(),route=useRoute(),router=useRouter(),session=useSessionStore(),requests=new LatestRequest()
const value=ref<WorkDocumentLibrary|null>(null),loading=ref(false),error=ref<unknown>(null),success=ref('')
const search=ref(''),kind=ref(''),page=ref(1),selectedId=ref(''),selectedOrigin=ref('')
const mode=ref<'source'|'batch'|null>(null),source=ref<InstanceType<typeof DocumentSourceForm>|null>(null),batch=ref<InstanceType<typeof DocumentBatchUpload>|null>(null),versionUpload=ref<InstanceType<typeof DocumentVersionUpload>|null>(null)
const historyPreview=ref('')
const retainedSelection=ref<WorkDocumentEntry|null>(null)
const selected=computed(()=>value.value?.results.find(item=>item.document.id===selectedId.value)??(retainedSelection.value?.document.id===selectedId.value?retainedSelection.value:null))
const origin=computed(()=>selected.value?.origins.find(item=>originKey(item)===selectedOrigin.value))
const preview=computed<BasisDocument|null>(()=>{
  if(!selected.value)return null
  return origin.value&&'accepted_version_id' in origin.value?{...selected.value.document,accepted_version_id:origin.value.accepted_version_id??null}:selected.value.document
})
const back=computed(()=>{
  const target=route.query.return,path=`/expertises/${encodeURIComponent(String(route.params.id))}`
  return typeof target==='string'&&(target===path||target.startsWith(path+'?'))?target:path
})
const detach=ref<{id:string;title:string;reason:string;version:number}|null>(null),detachAttempt=ref<{key:string;body:Record<string,unknown>}|null>(null),detachBusy=ref(false),detachConflict=ref(false),detachError=ref<unknown>(null)
const dirty=computed(()=>Boolean(source.value?.dirty||batch.value?.dirty||versionUpload.value?.dirty||detach.value))
const anyBusy=computed(()=>Boolean(source.value?.busy||batch.value?.busy||versionUpload.value?.busy||detachBusy.value))
const confirmLeave=useDirtyGuard(()=>dirty.value,router)
function apply(data:WorkDocumentLibrary){
  const previous=selected.value
  value.value=data
  if(data.results.some(item=>item.document.id===selectedId.value)){retainedSelection.value=null;return}
  if(previous&&(versionUpload.value?.dirty||versionUpload.value?.busy)){retainedSelection.value=previous;return}
  retainedSelection.value=null;selectedId.value=data.results[0]?.document.id??''
}
async function load(){
  loading.value=true;error.value=null
  const query=new URLSearchParams({page:String(page.value)});if(search.value.trim())query.set('search',search.value.trim());if(kind.value)query.set('kind',kind.value)
  try{await requests.run(signal=>api.request<WorkDocumentLibrary>(documentPath(String(route.params.id))+'?'+query,{signal}),data=>{apply(data);loading.value=false})}
  catch(cause){error.value=cause;loading.value=false}
}
function filter(){page.value=1;void load()}
function saved(response:WorkDocumentResponse){
  requests.cancel();loading.value=false
  if(value.value&&(search.value.trim()||kind.value||page.value>1)){
    value.value={...value.value,context:response.library.context,can_link:response.library.can_link,can_unlink:response.library.can_unlink,can_create:response.library.can_create}
    void load()
  }else apply(response.library)
  success.value='Изменение архива сохранено. Основание, принятый итог и факты выдачи не изменены.';if(mode.value==='source')mode.value=null
}
function openMode(next:'source'|'batch'){if(anyBusy.value||!confirmLeave())return;mode.value=next;success.value=''}
function close(){if(!anyBusy.value&&confirmLeave())mode.value=null}
function choose(row:WorkDocumentEntry){if(anyBusy.value||versionUpload.value?.dirty&&!window.confirm('Есть выбранный несохранённый файл версии. Перейти к другому документу?'))return;selectedId.value=row.document.id}
function startDetach(id:string){if(!value.value||!selected.value||anyBusy.value)return;detach.value={id,title:selected.value.document.title,reason:'',version:value.value.context.version};detachAttempt.value=null;detachConflict.value=false;detachError.value=null}
async function saveDetach(){
  if(!detach.value||detachBusy.value||detachConflict.value||!value.value?.can_unlink)return
  if(!detach.value.reason.trim()){detachError.value=new ApiError(400,'validation_error','Укажите причину снятия связи.');return}
  if(!detachAttempt.value)detachAttempt.value={key:newCommandKey(),body:{expected_version:detach.value.version,reason:detach.value.reason.trim()}}
  detachBusy.value=true;detachError.value=null
  try{const result=await api.request<WorkDocumentResponse>(documentPath(String(route.params.id))+detach.value.id+'/detach/',{method:'POST',body:detachAttempt.value.body,headers:{'Idempotency-Key':detachAttempt.value.key}});detach.value=null;detachAttempt.value=null;saved(result)}
  catch(cause){detachError.value=cause;detachConflict.value=cause instanceof ApiError&&cause.status===409}finally{detachBusy.value=false}
}
function acceptDetach(){if(!value.value||!detach.value||!detachAttempt.value)return;detach.value.version=value.value.context.version;detachAttempt.value={key:newCommandKey(),body:{...detachAttempt.value.body,expected_version:detach.value.version}};detachConflict.value=false;detachError.value=null}
watch(selected,(row,previous)=>{
  if(!row){selectedOrigin.value='';return}
  if(row.document.id!==previous?.document.id||!row.origins.some(item=>originKey(item)===selectedOrigin.value)&&selectedOrigin.value!=='latest'){
    const preferred=[...row.origins].reverse().find(item=>'accepted_version_id' in item)??row.origins[0]
    selectedOrigin.value=preferred?originKey(preferred):'latest'
  }
},{immediate:true})
watch(()=>route.params.id,()=>{mode.value=null;value.value=null;retainedSelection.value=null;selectedId.value='';selectedOrigin.value='';success.value='';page.value=1;void load()},{immediate:true})
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Единый архив документов</p><h1>{{value?.context.registration_number||'Документы экспертизы'}}</h1><p class="muted">Основания, результаты, переписка и дополнительные файлы — без копий на каждый номер.</p></div><RouterLink data-archive-back :to="back">← К карточке экспертизы</RouterLink></div>
  <ApiMessage :error="error"/><p v-if="loading" class="state" role="status">Загрузка архива…</p><p v-if="success" class="message message-success" role="status">{{success}}</p>
  <section v-if="value" class="card">
    <div class="section-heading"><div><h2>Документы и связи</h2><p class="muted compact">Версия работы {{value.context.version}} · {{value.count}} документов по текущему фильтру</p></div><div class="button-row"><button type="button" @click="load">Обновить архив</button><button v-if="value.can_link" data-open-document-source class="button-primary" type="button" :disabled="anyBusy" @click="openMode('source')">Добавить документ</button><button v-if="value.can_link&&value.can_create" type="button" :disabled="anyBusy" @click="openMode('batch')">Загрузить файлы / папку</button></div></div>
    <p v-if="!value.can_link" class="muted">Только просмотр. Для добавления связи требуется отдельное право «Связывать документы с экспертизой»; автоматически оно не выдаётся.</p>
    <form data-archive-filters class="form-columns" @submit.prevent="filter"><label>Поиск по названию<input v-model="search" name="archive_search"/></label><label>Вид документа<select v-model="kind" name="archive_kind"><option value="">Все виды</option><option v-for="option in value.document_kinds" :key="option.code" :value="option.code">{{option.name}}</option></select></label><button type="submit">Применить фильтры</button></form>
    <div v-if="mode" class="inset-form"><div class="section-heading"><h2>{{mode==='batch'?'Пакетная загрузка':'Дополнительная связь'}}</h2><button type="button" :disabled="anyBusy" @click="close">Закрыть форму</button></div>
      <DocumentSourceForm v-if="mode==='source'" ref="source" :work-id="value.context.id" :expected-version="value.context.version" :department-id="value.context.department.id" :kind-options="value.document_kinds" :authorized="value.can_link" :allow-create="value.can_create" @saved="saved" @refresh="load"/>
      <DocumentBatchUpload v-else ref="batch" :work-id="value.context.id" :expected-version="value.context.version" :department-id="value.context.department.id" :kind-options="value.document_kinds" :authorized="value.can_link" :allow-create="value.can_create" @saved="saved" @refresh="load"/>
    </div>
    <div class="archive-layout">
      <aside class="archive-list"><p v-if="!value.results.length" class="state">По текущему фильтру доступных документов нет.</p><button v-for="row in value.results" :key="row.document.id" type="button" class="archive-document" :class="{'archive-document-selected':row.document.id===selectedId}" :aria-pressed="row.document.id===selectedId" @click="choose(row)"><strong>{{row.document.title}}</strong><small>{{value.document_kinds.find(item=>item.code===row.document.kind)?.name||row.document.kind}} · {{row.document.versions.length}} версий</small><span v-for="item in row.origins" :key="originKey(item)" class="muted">{{item.label}}</span></button><div class="pagination"><button v-if="value.previous" type="button" @click="page--;load()">← Предыдущая</button><span>Страница {{page}}</span><button v-if="value.next" type="button" @click="page++;load()">Следующая →</button></div></aside>
      <section v-if="selected" class="archive-preview">
        <p v-if="retainedSelection" class="message">Документ не попал в последнее обновление списка. Выбранный несохранённый файл сохранён в форме; доступ и версия будут повторно проверены сервером при загрузке.</p>
        <label>Контекст просмотра<select v-model="selectedOrigin" name="archive_origin"><option v-for="item in selected.origins" :key="originKey(item)" :value="originKey(item)">{{item.label}}</option><option value="latest">Общий просмотр · последние версии</option></select></label>
        <p v-if="selectedOrigin==='latest'&&selected.origins.some(item=>'accepted_version_id' in item)" class="message">Общий просмотр не меняет файл, принятый конкретным событием. Выберите событие выше для его подтверждённой версии.</p>
        <BasisPreview :document="preview" heading="Документ архива" :accepted-label="origin?.label"/>
        <DocumentVersionUpload v-if="session.can('documents.upload')" :key="selected.document.id" ref="versionUpload" :document="selected.document" :authorized="session.can('documents.upload')" @saved="load"/>
        <div v-if="selected.extra_links.length" class="inset-form"><h4>Дополнительные связи этой работы</h4><div v-for="item in selected.extra_links" :key="item.id"><p>{{item.note||'Дополнительный документ'}}</p><button v-if="value.can_unlink" type="button" :data-detach-link="item.id" :disabled="anyBusy" @click="startDetach(item.id)">Снять эту связь</button></div><p class="muted compact">Файл и связи с другими работами не удаляются. Основание поступления и другие процессные связи здесь снять нельзя.</p></div>
      </section>
    </div>
    <form v-if="detach" data-detach-document class="inset-form form-grid" @submit.prevent="saveDetach"><h3>Снять дополнительную связь</h3><p>{{detach.title}}</p><label>Причина<textarea v-model="detach.reason" :disabled="detachBusy||Boolean(detachAttempt)" required/></label><ApiMessage :error="detachError"/><div v-if="detachConflict" class="message"><button type="button" @click="load">Обновить архив для сверки</button><button type="button" @click="acceptDetach">Принять версию {{value.context.version}} работы</button></div><div class="button-row"><button type="submit" :disabled="detachBusy||detachConflict||!value.can_unlink">{{detachAttempt?'Повторить ту же попытку':'Снять связь, не удаляя файл'}}</button><button type="button" :disabled="detachBusy" @click="detach=null;detachAttempt=null">Отмена</button></div></form>
    <details v-if="value.detached_links.length" class="inset-form"><summary>История снятых связей · {{value.detached_links.length}}</summary><article v-for="item in value.detached_links" :key="item.id"><strong>{{item.document&&'title' in item.document?item.document.title:'Документ ограниченного доступа'}}</strong><p>{{item.detach_reason}}</p><small>{{new Date(item.detached_at).toLocaleString('ru-RU')}}</small><button v-if="item.document&& !('restricted' in item.document)" type="button" :data-history-preview="item.id" @click="historyPreview=historyPreview===item.id?'':item.id">{{historyPreview===item.id?'Закрыть просмотр':'Просмотреть документ из истории'}}</button><BasisPreview v-if="historyPreview===item.id" :document="item.document" heading="Документ снятой дополнительной связи"/></article></details>
  </section>
  <p v-else-if="!loading" class="state"><button type="button" @click="load">Повторить загрузку архива</button></p>
</template>
<style scoped>
.archive-layout{display:grid;grid-template-columns:minmax(230px,.72fr) minmax(0,1.6fr);gap:28px;margin-top:28px;align-items:start}.archive-list,.archive-preview{min-width:0}.archive-document{display:flex;flex-direction:column;gap:7px;text-align:left;width:100%;margin-bottom:10px;padding:16px;white-space:normal;overflow-wrap:anywhere;background:#fafbf8}.archive-document-selected{border-color:var(--green,#547244);background:#edf3e7;box-shadow:inset 3px 0 #547244}.archive-document small{font-size:11px}.archive-document span{font-size:11px}.archive-preview :deep(iframe){margin-top:16px}.archive-picker{display:grid;gap:8px}.archive-preview :deep(p),.archive-preview :deep(strong){overflow-wrap:anywhere}@media(max-width:1100px){.archive-layout{grid-template-columns:1fr}.archive-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.archive-list .pagination{grid-column:1/-1}}@media(max-width:600px){.archive-list{grid-template-columns:1fr}.archive-layout{gap:16px}.archive-document{margin:0}}
</style>
