<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { Expertise,ExpertiseCommandResponse,HistoricalReportOptions,HistoricalReportPayload,Reference,ResultKind } from '../../api/types'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import HistoryReportDetails from './HistoryReportDetails.vue'
const props=defineProps<{expertise:Expertise}>(),emit=defineEmits<{updated:[Expertise]}>()
const api=useApi(),router=useRouter(),requests=new LatestRequest()
const editing=ref(false),busy=ref(false),uncertain=ref(false),loading=ref(false),error=ref<unknown>(null),optionsError=ref<unknown>(null)
const options=ref<HistoricalReportOptions|null>(null),reason=ref(''),specialtyId=ref(''),expectedVersion=ref(0),initial=ref('')
const kind=ref<ResultKind|''>(''),completedOn=ref(''),complexity=ref(''),q=ref(''),r=ref(''),s=ref(''),t=ref(''),statistics=ref(false)
const sndz=ref(''),sndzComment=ref(''),allocationsComplete=ref(false),note=ref(''),decidedOn=ref(''),returnReason=ref(''),returnComment=ref('')
const allocations=ref<{reason_id:string;count:string;comment:string;document_id:string}[]>([])
const attempt=ref<{path:string;key:string;body:HistoricalReportPayload}|null>(null)
const history=computed(()=>props.expertise.historical!),isReturn=computed(()=>props.expertise.state==='without_execution')
const eligible=computed(()=>props.expertise.origin_kind==='historical'&&!history.value.operational&&['completed','without_execution'].includes(props.expertise.state))
const authorized=computed(()=>eligible.value&&props.expertise.allowed_actions.includes('expertise.closed.correct'))
const recovering=computed(()=>uncertain.value&&Boolean(attempt.value))
const numeric=(value:string)=>value===''?null:Number(value)
const numberFields=[{name:'questions',label:'Q — поставленные вопросы',value:q},{name:'categorical',label:'R — категорические ответы',value:r},{name:'probable',label:'S — вероятные ответы',value:s},{name:'unresolved',label:'T — нерешённые вопросы',value:t}]
const body=computed<HistoricalReportPayload>(()=>({expected_version:expectedVersion.value,reason:reason.value.trim(),specialty_id:specialtyId.value||null,correction_kind:isReturn.value?'return':'result',
 ...(isReturn.value?{return_data:{decided_on:decidedOn.value||null,return_reason_id:returnReason.value||null,comment:returnComment.value.trim()}}:{result:{kind:kind.value||null,completed_on:completedOn.value||null,complexity_level:numeric(complexity.value),questions:numeric(q.value),categorical:numeric(r.value),probable:numeric(s.value),unresolved:numeric(t.value),statistics_complete:statistics.value,sndz_reason_id:kind.value==='sndz'?sndz.value||null:null,sndz_comment:kind.value==='sndz'?sndzComment.value.trim():'',unresolved_allocations:allocations.value.map(item=>({reason_id:item.reason_id,count:Number(item.count),comment:item.comment.trim(),document_id:item.document_id||null})),allocations_complete:allocationsComplete.value,note:note.value.trim()}})}))
const stamp=computed(()=>JSON.stringify(body.value))
const dirty=computed(()=>editing.value&&(stamp.value!==initial.value||Boolean(attempt.value)))
const confirmLeave=useDirtyGuard(()=>dirty.value||busy.value,router)
watch(stamp,()=>{if(!busy.value&&!uncertain.value){attempt.value=null;error.value=null}},{flush:'sync'})
const conflict=computed(()=>error.value instanceof ApiError&&error.value.status===409)
const validation=computed(()=>{
 if(!reason.value.trim())return 'Укажите основание уточнения.'
 if(isReturn.value){if(options.value?.return_reasons.find(item=>item.id===returnReason.value)?.code==='other'&&!returnComment.value.trim())return 'Поясните иную причину возврата.';return ''}
 const numbers=[complexity.value,q.value,r.value,s.value,t.value]
 if(numbers.some(value=>value!==''&&(!Number.isSafeInteger(Number(value))||Number(value)<0))||(complexity.value!==''&&Number(complexity.value)<1))return 'Числа должны быть целыми и неотрицательными, сложность — не меньше 1.'
 const parts=[numeric(r.value),numeric(s.value),numeric(t.value)],question=numeric(q.value),sum=parts.reduce<number>((a,n)=>a+(n??0),0)
 if(question!==null&&(sum>question||(parts.every(n=>n!==null)&&sum!==question)))return 'Проверьте равенство Q = R + S + T.'
 if(statistics.value&&(question===null||parts.some(n=>n===null)))return 'Для подтверждения полноты заполните Q, R, S и T, включая нули.'
 const seen=new Set<string>();let allocated=0
 for(const item of allocations.value){if(!item.reason_id||seen.has(item.reason_id)||!Number.isSafeInteger(Number(item.count))||Number(item.count)<1)return 'Проверьте причины и положительные целые количества.';seen.add(item.reason_id);allocated+=Number(item.count);if(options.value?.unresolved_reasons.find(ref=>ref.id===item.reason_id)?.code==='other'&&!item.comment.trim())return 'Поясните иную причину нерешённых вопросов.'}
 if(numeric(t.value)!==null&&allocated>Number(t.value))return 'Распределение превышает T.'
 if(allocationsComplete.value&&(numeric(t.value)===null||allocated!==Number(t.value)))return 'Полное распределение должно равняться T.'
 return ''
})
const valid=computed(()=>recovering.value||authorized.value&&!loading.value&&!optionsError.value&&!validation.value&&!conflict.value)
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Krasnoyarsk',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
function catalog(items:Reference[]|undefined,currentIds:(string|undefined)[]){
 const retained=new Set(currentIds)
 // Previously used inactive references remain inspectable/restorable.
 for(const c of history.value.corrections??[])for(const state of [c.before,c.after])for(const value of Object.values(state)){
  if(value&&typeof value==='object'&&!Array.isArray(value)&&'id' in value)retained.add(String(value.id))
  if(Array.isArray(value))for(const item of value)if(item.reason?.id)retained.add(item.reason.id)
 }
 return (items??[]).filter(item=>item.is_active||retained.has(item.id))
}
const specialties=computed(()=>catalog(options.value?.specialties,[props.expertise.specialty?.id]))
const sndzReasons=computed(()=>catalog(options.value?.sndz_reasons,[history.value.report_details?.sndz_reason?.id]))
const returnReasons=computed(()=>catalog(options.value?.return_reasons,[history.value.report_details?.return_reason?.id]))
const unresolvedReasons=computed(()=>catalog(options.value?.unresolved_reasons,history.value.report_details?.unresolved_allocations.map(item=>item.reason.id)??[]))
let active=true
async function loadOptions(){loading.value=true;optionsError.value=null;try{await requests.run(signal=>api.request<HistoricalReportOptions>(`/expertises/${props.expertise.id}/history-report/`,{signal}),value=>{options.value=value;loading.value=false})}catch(cause){optionsError.value=cause;loading.value=false}}
async function start(){
 if(!authorized.value)return
 const h=history.value,details=h.report_details
 expectedVersion.value=props.expertise.version;reason.value='';specialtyId.value=props.expertise.specialty?.id??'';kind.value=h.result_kind??'';completedOn.value=h.completed_on??'';complexity.value=h.complexity_level==null?'':String(h.complexity_level)
 q.value=h.questions==null?'':String(h.questions);r.value=h.categorical==null?'':String(h.categorical);s.value=h.probable==null?'':String(h.probable);t.value=h.unresolved==null?'':String(h.unresolved);statistics.value=h.statistics_confirmed
 sndz.value=details?.sndz_reason?.id??'';sndzComment.value=details?.sndz_comment??'';allocationsComplete.value=details?.allocations_complete??false;note.value=details?.note??''
 allocations.value=(details?.unresolved_allocations??[]).map(item=>({reason_id:item.reason.id,count:String(item.count),comment:item.comment,document_id:item.document?.id??''}))
 decidedOn.value=h.return_decided_on??'';returnReason.value=details?.return_reason?.id??'';returnComment.value=details?.return_comment??''
 attempt.value=null;uncertain.value=false;error.value=null;editing.value=true;initial.value=stamp.value;await loadOptions()
}
function acceptVersion(){if(!busy.value&&!uncertain.value){expectedVersion.value=props.expertise.version;attempt.value=null;error.value=null}}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave()){editing.value=false;attempt.value=null;error.value=null;requests.cancel()}}
async function submit(){
 if(busy.value||!valid.value)return
 busy.value=true;error.value=null
 try{
  if(!attempt.value)attempt.value={path:`/expertises/${props.expertise.id}/history-report/`,key:newCommandKey(),body:JSON.parse(JSON.stringify(body.value))}
  const response=await api.request<ExpertiseCommandResponse>(attempt.value.path,{method:'POST',body:attempt.value.body,headers:{'Idempotency-Key':attempt.value.key}})
  if(!active)return
  editing.value=false;attempt.value=null;uncertain.value=false;emit('updated',response.expertise)
 }catch(cause){if(active){error.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}}finally{if(active)busy.value=false}
}
onBeforeUnmount(()=>{active=false;requests.cancel()})
</script>
<template>
 <section class="card stack-card" data-history-report-panel>
  <div class="section-heading"><div><p class="eyebrow">Отчётные сведения старой работы</p><h2>Уточнение без повторного завершения <HelpTip label="Редактирование исторических сведений">Номер, состояние, фактический отдел и исполнители сохраняются. Это не создание нового заключения или выдачи.</HelpTip></h2></div><button v-if="authorized&&!editing" data-history-report-edit @click="start">Редактировать отчётные сведения</button></div>
  <HistoryReportDetails :history="history"/>
  <p v-if="!editing&&!authorized" class="muted compact">Редактирование недоступно для ваших прав. <HelpTip label="Права редактирования">Уточнение доступно ответственному пользователю с правом корректировки закрытой работы и подходящей областью доступа.</HelpTip></p>
  <form v-if="editing" data-history-report-form class="inset-form form-grid" @submit.prevent="submit">
   <h3>{{isReturn?'Уточнить решение без исполнения':'Уточнить исторический результат'}}</h3>
   <ApiMessage :error="error"/><ApiMessage :error="optionsError"/>
   <p v-if="loading" role="status" class="muted">Загрузка справочников…</p><button v-if="optionsError" type="button" @click="loadOptions">Повторить загрузку справочников</button>
   <p v-if="recovering" class="message">Ответ не получен. Исходный пакет и ключ сохранены; повтор не создаёт второе уточнение.</p>
   <p v-if="!authorized" class="message message-error">Право уточнения больше не разрешено. Введённые сведения сохранены в форме.</p>
   <p v-if="conflict&&!recovering" class="message">Обновите серверные сведения карточки. Ввод сохранён. <button v-if="expectedVersion!==expertise.version" data-history-report-accept-version type="button" @click="acceptVersion">Принять версию {{expertise.version}} для новой попытки</button></p>
   <fieldset class="form-grid" :disabled="busy||recovering||!authorized">
    <label>Специальность<select v-model="specialtyId" name="history_report_specialty"><option value="">Неизвестна / не уточнена</option><option v-for="item in specialties" :key="item.id" :value="item.id">{{item.code}} · {{item.name}}{{item.is_active?'':' (неактивна, использовалась ранее)'}}</option></select></label>
    <template v-if="!isReturn">
     <div class="form-columns"><label>Вид исторического результата<select v-model="kind" name="history_report_kind"><option value="">Неизвестен</option><template v-if="expertise.category_code==='6'"><option value="research_act">Акт экспертного исследования</option></template><template v-else><option value="expert_conclusion">Заключение эксперта</option><option value="sndz">Сообщение о невозможности дать заключение</option></template></select></label><label>Дата окончания, если известна<input v-model="completedOn" name="history_report_completed_on" type="date" :min="expertise.receipt.received_at" :max="today()"/></label><label>Уровень сложности<input v-model="complexity" name="history_report_complexity" type="number" min="1" step="1"/></label></div>
     <HelpTip label="Неизвестные числовые сведения">Пустое поле — неизвестное значение. 0 — известное отсутствие. Ничего не дополняется автоматически.</HelpTip>
     <div class="form-columns"><label v-for="field in numberFields" :key="field.name">{{field.label}}<input v-model="field.value.value" :name="`history_report_${field.name}`" type="number" min="0" step="1"/></label></div>
     <label class="check-label"><input v-model="statistics" name="history_report_statistics" type="checkbox"/>Подтверждаю полноту Q = R + S + T</label>
     <template v-if="kind==='sndz'"><label>Причина полного СНДЗ<select v-model="sndz" name="history_report_sndz_reason"><option value="">Неизвестна / не уточнена</option><option v-for="item in sndzReasons" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Пояснение к СНДЗ<textarea v-model="sndzComment" name="history_report_sndz_comment" rows="2"/></label></template>
     <section class="subsection"><h4>Причины нерешённых вопросов T</h4>
      <div v-for="(item,index) in allocations" :key="index" class="inset-form form-grid"><div class="form-columns"><label>Причина<select v-model="item.reason_id" :name="`history_allocation_reason_${index}`"><option value="">Выберите причину</option><option v-for="ref in unresolvedReasons" :key="ref.id" :value="ref.id">{{ref.name}}</option></select></label><label>Количество<input v-model="item.count" :name="`history_allocation_count_${index}`" type="number" min="1" step="1"/></label></div><label>Пояснение<textarea v-model="item.comment" :name="`history_allocation_comment_${index}`" rows="2"/></label><p v-if="item.document_id" class="muted compact">Сохранена ссылка на подтверждающий документ. <button type="button" @click="item.document_id=''">Убрать ссылку из уточнения</button></p><button type="button" class="align-start" @click="allocations.splice(index,1)">Убрать строку распределения</button></div>
      <button data-history-add-allocation type="button" class="align-start" @click="allocations.push({reason_id:'',count:'',comment:'',document_id:''})">Добавить причину</button><label class="check-label"><input v-model="allocationsComplete" name="history_report_allocations_complete" type="checkbox"/>Подтверждаю полное распределение T</label>
     </section>
     <label>Отчётное примечание<textarea v-model="note" name="history_report_note" rows="2"/></label>
    </template>
    <template v-else><label>Дата решения, если известна<input v-model="decidedOn" name="history_report_decided_on" type="date" :min="expertise.receipt.received_at" :max="today()"/></label><label>Причина решения без исполнения<select v-model="returnReason" name="history_report_return_reason"><option value="">Неизвестна / не уточнена</option><option v-for="item in returnReasons" :key="item.id" :value="item.id">{{item.name}}</option></select></label><label>Пояснение к решению<textarea v-model="returnComment" name="history_report_return_comment" rows="2"/></label><HelpTip label="Дата решения">Пустая дата остаётся неизвестной. Дата выдачи не подставляется вместо даты решения.</HelpTip></template>
    <label>Основание уточнения<textarea v-model="reason" name="history_report_reason" rows="3" required/></label>
   </fieldset>
   <p v-if="validation&&!recovering" class="muted" role="status">{{validation}}</p>
   <div class="button-row"><button data-history-report-submit class="button-primary" :disabled="busy||!valid" :formnovalidate="recovering">{{busy?'Сохранение…':recovering?'Повторить ту же попытку':'Сохранить уточнение'}}</button><button type="button" :disabled="busy||recovering" @click="cancel">Отмена</button></div>
  </form>
 </section>
</template>
