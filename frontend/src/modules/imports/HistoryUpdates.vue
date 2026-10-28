<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { ImportApplication,ReconciliationOptions,ReconciliationRow,UpdatePayload } from '../../api/imports'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import ApplicationResult from './ApplicationResult.vue'
const props=defineProps<{batchId:string;items:ReconciliationRow[];canApply:boolean;options:ReconciliationOptions|null}>()
const emit=defineEmits<{applied:[]}>(),api=useApi(),router=useRouter()
const selected=ref<Record<string,UpdatePayload['updates'][number]&{number:string}>>({}),reason=ref(''),busy=ref(false),uncertain=ref(false),error=ref<unknown>(null)
const result=ref<ImportApplication|null>(null),numbers=ref<Record<string,string>>({}),attempt=ref<{key:string;body:UpdatePayload}|null>(null)
const candidates=computed(()=>props.items.filter(item=>item.update_preview))
let active=true
useDirtyGuard(()=>Boolean(Object.keys(selected.value).length||reason.value.trim()||busy.value||attempt.value),router)
const labels:Record<string,string>={complexity_level:'Категория сложности',specialty_id:'Специальность',employee_ids:'Исторические участники',state:'Состояние',completed_on:'Дата окончания',return_decided_on:'Дата решения без исполнения',issued_on:'Историческая дата выдачи',questions:'Поставлено вопросов',categorical:'Категорические ответы',probable:'Вероятные ответы',unresolved:'Не разрешено',inventory:'Опись',result_kind:'Вид результата',received_on:'Дата поступления',sender_name:'Отправитель',historical_number:'Прежний номер',statistics_confirmed:'Подтверждённая статистика',executor_raw:'Исполнитель в источнике',amount:'Сумма',authority_type:'Вид органа',authority_name:'Орган назначения',official:'Должностное лицо',contact:'Контакты',basis_text:'Основание',case_description:'Описание дела',unresolved_note:'Отметка о нерешённых вопросах',unresolved_reason_raw:'Причина в источнике',notes:'Отметки',delivery:'Передача'}
const values:Record<string,string>={completed:'Завершена',without_execution:'Без исполнения',in_progress:'В работе',suspended:'Приостановлена',expert_conclusion:'Заключение эксперта',research_act:'Акт исследования',sndz:'СНДЗ'}
function show(field:string,value:unknown){
 if(value===null||value===undefined||value==='')return 'Неизвестно / не заполнено'
 if(typeof value==='boolean')return value?'Да':'Нет'
 if(field==='specialty_id')return props.options?.specialties.find(s=>s.id===value)?.code??String(value)
 if(Array.isArray(value))return props.options?value.map(id=>props.options?.employees.find(p=>p.id===id)?.full_name??'Участник источника').join(', ')||'Нет выбранных участников':`Участников: ${value.length}`
 return values[String(value)]??String(value)
}
function resetAttempt(){attempt.value=null;uncertain.value=false;error.value=null}
watch(reason,()=>{
 if(uncertain.value){
  const frozen=attempt.value?.body.reason
  if(frozen!==undefined&&reason.value!==frozen)reason.value=frozen
  return
 }
 resetAttempt()
},{flush:'sync'})
function choose(item:ReconciliationRow,on:boolean){
 const info=item.update_preview
 if(busy.value||uncertain.value||!props.canApply||!info?.eligible||!info.expected_source_row_id||!item.selection)return
 if(on)selected.value[item.row.id]={row_id:item.row.id,expected_selection_version:item.selection.version,expected_work_version:info.expected_work_version,expected_source_row_id:info.expected_source_row_id,number:String(item.row.facts.registration_number)}
 else delete selected.value[item.row.id]
 resetAttempt()
}
async function submit(){
 if(busy.value||(!props.canApply&&!uncertain.value)||!reason.value.trim()||!Object.keys(selected.value).length)return
 busy.value=true;error.value=null
 try{
  if(!attempt.value)attempt.value={key:newCommandKey(),body:{reason:reason.value.trim(),updates:Object.values(selected.value).sort((a,b)=>a.row_id.localeCompare(b.row_id)).map(({number,...entry})=>entry)}}
  const response=await api.request<{application:ImportApplication}>(`/imports/${props.batchId}/updates/`,{method:'POST',body:attempt.value.body,headers:{'Idempotency-Key':attempt.value.key}})
  if(!active)return
  numbers.value=Object.fromEntries(Object.values(selected.value).map(entry=>[entry.row_id,entry.number]));result.value=response.application
  resetAttempt();selected.value={};reason.value='';emit('applied')
 }catch(cause){if(active){error.value=cause;uncertain.value=uncertain.value||!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}}
 finally{if(active)busy.value=false}
}
onBeforeUnmount(()=>{active=false})
</script>
<template>
 <ApplicationResult v-if="result" :application="result" :numbers="numbers"/>
 <section v-if="candidates.length||Object.keys(selected).length" class="card stack-card" data-history-updates>
  <div><p class="eyebrow">Исправления нового снимка</p><h2>Обновление исторических записей</h2><p class="muted">Это отдельный пакет: номера сохраняются, новые экспертизы и события производства не создаются. Ручная правка или продолжение в АИС блокируют обновление всей выбранной группы.</p></div>
  <article v-for="item in candidates" :key="item.row.id" class="update-item">
   <div class="section-heading"><h3>{{item.row.facts.registration_number}}</h3><label v-if="canApply" class="check-label"><input data-update-row type="checkbox" :aria-label="`Обновить ${item.row.facts.registration_number}`" :checked="Boolean(selected[item.row.id])" :disabled="busy||uncertain||!item.selection||!item.update_preview?.eligible" @change="choose(item,($event.target as HTMLInputElement).checked)"/>В пакет обновления</label></div>
   <p v-if="!item.selection" class="message">Сначала подтвердите новое сопоставление в таблице выше. Прежний выбор — только заготовка.</p>
   <p v-for="blocker in item.update_preview!.blockers" :key="blocker" class="message message-error">{{blocker}}</p>
   <div class="table-scroll"><table><thead><tr><th>Сведение</th><th>В рабочей базе</th><th>После подтверждения</th></tr></thead><tbody><tr v-for="change in item.update_preview!.changes" :key="change.field"><th>{{labels[change.field]??change.field}}</th><td>{{change.before_label??show(change.field,change.before)}}</td><td>{{change.after_label??show(change.field,change.after)}}</td></tr></tbody></table></div>
   <p v-if="!item.update_preview!.changes.length" class="muted">Изменились сведения источника; типизированные рабочие поля совпадают.</p>
  </article>
  <form v-if="Object.keys(selected).length" data-update-form class="form-grid" @submit.prevent="submit">
   <h3>Обновить выбранные записи · {{Object.keys(selected).length}}</h3><ul><li v-for="entry in selected" :key="entry.row_id">{{entry.number}} · версия работы {{entry.expected_work_version}} · выбор {{entry.expected_selection_version}}</li></ul>
   <ApiMessage :error="error"/><p v-if="uncertain" class="message">Ответ не получен. Повтор отправляет прежний пакет и ключ; не создавайте второй пакет для той же попытки.</p>
   <label>Основание исправлений<textarea v-model="reason" name="update_reason" required rows="2" :disabled="busy||uncertain||!canApply"/></label>
   <button class="button-primary align-start" :disabled="busy||(!canApply&&!uncertain)||!reason.trim()">{{busy?'Обновление…':uncertain?'Повторить ту же попытку':'Подтвердить обновление записей'}}</button>
  </form>
 </section>
</template>
<style scoped>
.update-item{padding:16px 0;border-top:1px solid var(--border)}.update-item h3{margin:0}.check-label{display:flex;align-items:center;gap:8px}.check-label input{width:18px;height:18px}td{white-space:pre-wrap;overflow-wrap:anywhere;max-width:520px;vertical-align:top}th{min-width:150px}.table-scroll{max-height:480px;overflow:auto}
</style>
