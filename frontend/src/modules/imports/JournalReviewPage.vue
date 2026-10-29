<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { RouterLink,useRoute,useRouter } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import { journalFieldLabels,journalValue,type JournalReview,type JournalReviewChoice,type JournalReviewResult,type JournalReviewRow } from '../../api/journalReview'
import { useSessionStore } from '../../stores/session'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import ApplicationResult from './ApplicationResult.vue'

const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter(),requests=new LatestRequest()
const enabled=computed(()=>session.importPreviewEnabled&&session.journalApplicationEnabled&&session.can('imports.results.view'))
const canApply=computed(()=>enabled.value&&session.can('imports.reconcile')&&session.can('imports.apply'))
const data=ref<JournalReview|null>(null),selected=ref<Record<string,string[]>>({}),loading=ref(false),error=ref<unknown>(null),writeError=ref<unknown>(null)
const busy=ref(false),uncertain=ref(false),result=ref<JournalReviewResult|null>(null),attempt=ref<{key:string;batchId:string;body:{selections:JournalReviewChoice[]}}|null>(null)
const locked=computed(()=>busy.value||uncertain.value||Boolean(result.value)),selectedCount=computed(()=>Object.keys(selected.value).length)
const allItems=computed(()=>(data.value?.results??[]).filter(item=>item.eligible&&(item.action==='create'||item.changes.length>0)))
const back=computed(()=>typeof route.query.return==='string'&&/^\/expertises(?:\?|$)/.test(route.query.return)?route.query.return:'/expertises')
let generation=0
const confirmLeave=useDirtyGuard(()=>Boolean(selectedCount.value||busy.value||uncertain.value),router)
async function load(){
 requests.cancel();data.value=null;loading.value=true;error.value=null
 if(!enabled.value){loading.value=false;return}
 const id=String(route.params.id)
 try{await requests.run(signal=>api.request<JournalReview>(`/imports/${id}/review/`,{signal}),value=>{data.value=value;loading.value=false})}
 catch(cause){error.value=cause;loading.value=false}
}
function choose(item:JournalReviewRow,field:string|null,on:boolean){
 if(locked.value||!canApply.value||!item.eligible)return
 if(field===null){if(on)selected.value[item.row_id]=[];else delete selected.value[item.row_id]}
 else{
  const fields=new Set(selected.value[item.row_id]??[])
  if(on)fields.add(field);else fields.delete(field)
  if(fields.size)selected.value[item.row_id]=[...fields];else delete selected.value[item.row_id]
 }
 attempt.value=null;writeError.value=null
}
function safe(){
 if(locked.value||!canApply.value)return
 const choices:Record<string,string[]>={}
 for(const item of data.value?.results??[]){
  if(!item.eligible)continue
  if(item.action==='create')choices[item.row_id]=[]
  else{const fields=item.changes.filter(change=>!change.conflict).map(change=>change.field);if(fields.length)choices[item.row_id]=fields}
 }
 selected.value=choices;attempt.value=null;writeError.value=null
}
function clear(){if(!locked.value){selected.value={};attempt.value=null;writeError.value=null}}
function acceptAll(){
 if(locked.value||!canApply.value||!allItems.value.length)return
 selected.value=Object.fromEntries(allItems.value.map(item=>[item.row_id,item.action==='create'?[]:item.changes.map(change=>change.field)]))
 attempt.value=null;writeError.value=null
}
async function refresh(){
 if(busy.value||uncertain.value||!confirmLeave())return
 selected.value={};attempt.value=null;result.value=null;writeError.value=null;await load()
}
async function apply(){
 if(busy.value||!selectedCount.value||result.value||!canApply.value)return
 const stamp=generation
 if(!attempt.value){
  const items=(data.value?.results??[]).filter(item=>Object.hasOwn(selected.value,item.row_id))
  const selections=items.map(item=>({row_id:item.row_id,action:item.action,
   expected_work_version:item.expected_work_version,expected_source_row_id:item.expected_source_row_id,expected_selection_version:item.expected_selection_version,
   proposal_hash:item.proposal_hash,accepted_fields:[...selected.value[item.row_id]!].sort()})).sort((a,b)=>a.row_id.localeCompare(b.row_id))
  const updates=items.filter(item=>item.action==='update'),fields=updates.flatMap(item=>item.changes.filter(change=>selected.value[item.row_id]!.includes(change.field)))
  const conflicts=fields.filter(change=>change.conflict).length
  const message=[
   'Применить выбранные изменения в БД?',
   `Новых экспертиз: ${items.length-updates.length}`,
   `Обновляемых экспертиз: ${updates.length}`,
   `Изменяемых полей: ${fields.length}`,
   `Ручных расхождений: ${conflicts}.${conflicts?' Эти значения в БД будут заменены значениями из таблицы.':''}`,
   `Заблокированных строк пропущено: ${(data.value?.results??[]).filter(item=>!item.eligible).length}`,
   'Неотмеченные поля и записи не затрагиваются. Продолжить?'
  ].join('\n')
  if(!window.confirm(message)||stamp!==generation||busy.value||result.value||!canApply.value)return
  attempt.value={key:newCommandKey(),batchId:String(route.params.id),body:{selections}}
 }
 const packet=attempt.value
 busy.value=true;writeError.value=null
 try{
  const response=await api.request<JournalReviewResult>(`/imports/${packet.batchId}/review/`,{method:'POST',body:packet.body,headers:{'Idempotency-Key':packet.key}})
  if(stamp!==generation)return
  if(response.batch_id!==packet.batchId||!Array.isArray(response.applications)||!Number.isInteger(response.created_count)||!Number.isInteger(response.updated_count))throw new ApiError(200,'invalid_response','Не получен протокол обновления. Повторите ту же попытку.')
  result.value=response;selected.value={};attempt.value=null;uncertain.value=false
 }catch(cause){if(stamp===generation){writeError.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response';if(!uncertain.value)attempt.value=null}}
 finally{if(stamp===generation)busy.value=false}
}
watch([()=>route.params.id,enabled],()=>{generation++;requests.cancel();selected.value={};attempt.value=null;result.value=null;writeError.value=null;busy.value=false;uncertain.value=false;void load()},{immediate:true})
onBeforeUnmount(()=>{generation++;requests.cancel()})
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Обновление рабочей базы</p><h1>Выберите изменения из журнала</h1><p class="muted">До подтверждения экспертизы в БД не меняются. Номера сохраняются, повторные записи не создаются.</p></div><RouterLink data-back-to-registry :to="back">← В реестр</RouterLink></div>
 <p v-if="!enabled" class="message">Для просмотра нужны доступ к источникам и поддержка импорта на сервере.</p>
 <template v-else>
  <ApiMessage :error="error"/><p v-if="loading" class="state">Сравнение с рабочей базой…</p>
  <section v-if="result" class="card stack-card" data-review-result><h2>Сохранённые в БД изменения</h2><p class="message message-success">Добавлено: {{result.created_count}} · Обновлено: {{result.updated_count}}</p><ApplicationResult v-for="application in result.applications" :key="application.id" :application="application" :numbers="Object.fromEntries((data?.results??[]).map(item=>[item.row_id,item.number]))"/></section>
  <section v-if="data" class="card stack-card">
   <div class="section-heading"><div class="button-row"><span class="badge">Новые: {{data.summary.new}}</span><span class="badge">Изменены: {{data.summary.changed}}</span><span class="badge">Совпадают: {{data.summary.unchanged}}</span><span class="badge badge-amber">Нужна проверка: {{data.summary.invalid}}</span></div><button :disabled="loading||busy||uncertain" @click="refresh">Обновить перечень</button></div>
   <p class="muted compact">«Обновить перечень» повторяет сравнение сохранённого снимка с БД. Для чтения новых исправлений таблицы запустите обновление из реестра.</p>
   <div v-if="canApply&&data.results.length&&!result" class="button-row"><button data-select-all-review :disabled="locked||!allItems.length" @click="acceptAll">Принять всё</button><button data-select-safe-review :disabled="locked" @click="safe">Выбрать изменения без конфликтов</button><button :disabled="locked||!selectedCount" @click="clear">Снять выбор</button></div>
   <p v-if="!data.results.length" class="state">Изменений нет — источник и рабочая база совпадают.</p>
   <p v-else-if="!result" class="message">«Принять всё» только отмечает все доступные изменения, включая ручные расхождения. Снимите лишние галочки и нажмите «Применить выбранное в БД»: запись произойдёт после подтверждения. «Выбрать изменения без конфликтов» не отмечает ручные расхождения.</p>
   <template v-if="!result"><article v-for="item in data.results" :key="item.row_id" class="review-item" :class="{'review-blocked':!item.eligible}">
    <div class="section-heading"><div><h2>{{item.number}}</h2><p class="muted compact">Строка {{item.source_row}} · {{item.action==='create'?'Новая экспертиза':'Изменения существующей экспертизы'}}</p></div><label v-if="canApply&&item.action==='create'&&item.eligible" class="check-label"><input :data-review-create="item.row_id" type="checkbox" :checked="Object.hasOwn(selected,item.row_id)" :disabled="locked" @change="choose(item,null,($event.target as HTMLInputElement).checked)"/>Добавить экспертизу целиком</label></div>
    <p v-for="blocker in item.blockers" :key="blocker" class="message message-error">{{blocker}}</p>
    <div class="table-scroll" v-if="item.changes.length"><table><thead><tr><th v-if="canApply&&item.action==='update'">Принять</th><th>Поле</th><th>Сейчас в БД</th><th>Из таблицы</th></tr></thead><tbody><tr v-for="change in item.changes" :key="change.field" :class="{'review-conflict':change.conflict}">
     <td v-if="canApply&&item.action==='update'"><input v-if="item.eligible" :data-review-field="`${item.row_id}:${change.field}`" type="checkbox" :aria-label="`Принять ${journalFieldLabels[change.field]??change.field} для ${item.number}`" :checked="selected[item.row_id]?.includes(change.field)??false" :disabled="locked" @change="choose(item,change.field,($event.target as HTMLInputElement).checked)"/></td>
     <th>{{journalFieldLabels[change.field]??change.field}}<small v-if="change.conflict" class="conflict-label">Ручное расхождение</small></th><td>{{change.before_label??journalValue(change.before)}}</td><td>{{change.after_label??journalValue(change.after)}}</td>
    </tr></tbody></table></div>
    <p v-else class="muted">Нет отдельных изменённых полей для принятия.</p>
    <details v-if="item.diagnostics.length"><summary>Замечания к исходной строке · {{item.diagnostics.length}}</summary><p v-for="(diagnostic,index) in item.diagnostics" :key="index" class="muted">{{diagnostic.columns.join(', ')}}: {{diagnostic.message}}</p></details>
    <div class="button-row"><RouterLink v-if="item.work_id&&session.can('expertise.view')" :to="`/expertises/${item.work_id}`">Открыть карточку</RouterLink><RouterLink :to="`/imports/${route.params.id}/reconciliation?search=${encodeURIComponent(item.number)}`">Подробная сверка и сопоставление</RouterLink></div>
   </article></template>
   <div v-if="canApply&&data.results.length&&!result" class="review-confirm stack-card"><ApiMessage :error="writeError"/><p v-if="uncertain" class="message">Ответ не получен. Выбор зафиксирован: повтор отправит те же поля и ключ, не создавая дублей.</p><p>Выбрано регистраций: {{selectedCount}}. Применятся только отмеченные поля и новые записи. Если данные успели измениться, весь пакет останется без изменений.</p><button data-apply-review class="button-primary align-start" :disabled="busy||!selectedCount" @click="apply">{{busy?'Обновление БД…':uncertain?'Повторить ту же попытку':'Применить выбранное в БД'}}</button></div>
  </section>
  <button v-if="error" :disabled="loading" @click="load">Повторить загрузку перечня</button>
 </template>
</template>
<style scoped>
.review-item{padding:24px 0;border-top:1px solid var(--border)}.review-item h2{margin:0 0 6px}.review-item .table-scroll{margin:14px 0}.review-item th{min-width:140px;text-align:left}.review-item td{min-width:130px;max-width:530px;white-space:pre-wrap;overflow-wrap:anywhere;vertical-align:top}.check-label{display:flex;align-items:center;gap:10px}.review-item input[type=checkbox]{width:19px;height:19px}.review-conflict{background:#fff8e8}.conflict-label{display:block;color:#8c5b18;margin-top:6px;font-weight:400}.review-confirm{border-top:1px solid var(--border);padding-top:20px}.section-heading{flex-wrap:wrap;gap:14px}.review-blocked{opacity:.9}
</style>
