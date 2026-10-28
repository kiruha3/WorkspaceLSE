<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {useRouter} from 'vue-router'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {canManageReportPlans} from '../../api/reportPlans'
import type {StateAssignmentPlan,StateAssignmentPlanPayload} from '../../api/types'
import {useSessionStore} from '../../stores/session'
import {useCommandAttempt,type CommandPacket} from '../../shared/ui/useCommandAttempt'
import {useDirtyGuard} from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import FactHistory from '../../shared/FactHistory.vue'
const props=defineProps<{year:number}>(),api=useApi(),session=useSessionStore(),router=useRouter(),requests=new LatestRequest()
const current=ref<StateAssignmentPlan|null>(null),loading=ref(false),loadError=ref<unknown>(null),editing=ref(false)
const canEdit=computed(()=>Boolean(current.value?.can_edit&&canManageReportPlans(session.user)))
const currentKnownSum=computed(()=>current.value?.lines.reduce((sum,line)=>sum+(line.count??0),0)??0)
const total=ref<string|number>(''),basis=ref(''),documentId=ref(''),documentMode=ref('existing'),reason=ref(''),expectedVersion=ref(0),initial=ref('')
type Line={key:number;specialty_id:string;count:string|number}
const lines=ref<Line[]>([]),documentForm=ref<InstanceType<typeof BasisDocumentForm>|null>(null);let sequence=0
let preparation:{packet:CommandPacket;newDocument:boolean}|null=null
// Vue also coerces type=number v-model without an explicit .number modifier.
const number=(value:string|number)=>String(value).trim()===''?null:Number(value)
const validNumber=(value:string|number)=>String(value).trim()===''||Number.isInteger(Number(value))&&Number(value)>=0&&Number(value)<=2147483647
const payload=computed<StateAssignmentPlanPayload>(()=>({expected_version:expectedVersion.value,reason:reason.value.trim(),total:number(total.value),basis_text:basis.value.trim(),document_id:documentId.value.trim()||null,lines:lines.value.map(line=>({specialty_id:line.specialty_id,count:number(line.count)}))}))
const stamp=computed(()=>JSON.stringify([total.value,basis.value,documentId.value,documentMode.value,reason.value,expectedVersion.value,lines.value]))
const knownSum=computed(()=>lines.value.reduce((sum,line)=>sum+(validNumber(line.count)?number(line.count)??0:0),0))
const balance=computed(()=>validNumber(total.value)&&number(total.value)!==null?number(total.value)!-knownSum.value:null)
const choices=computed(()=>current.value?.specialties.filter(item=>item.is_active||current.value?.retained_specialty_ids.includes(item.id))??[])
const command=useCommandAttempt<StateAssignmentPlan>(async()=>{
 if(!preparation)preparation={packet:{path:`/report-plans/${props.year}/`,method:'POST',body:JSON.parse(JSON.stringify(payload.value))},newDocument:documentMode.value==='new'}
 if(preparation.newDocument){if(!documentForm.value)throw new ApiError(400,'validation_error','Форма документа плана недоступна.');(preparation.packet.body as StateAssignmentPlanPayload).document_id=(await documentForm.value.persist()).id}
 return preparation.packet
},response=>{current.value=response;editing.value=false;preparation=null})
const {busy,uncertain,error}=command
const conflict=computed(()=>command.conflict.value&&!(error.value instanceof ApiError&&error.value.code==='document_version_conflict'))
function reset(){if(!busy.value&&!uncertain.value){preparation=null;command.reset()}}
watch(stamp,reset,{flush:'sync'})
const confirmLeave=useDirtyGuard(()=>busy.value||editing.value&&(stamp.value!==initial.value||Boolean(documentForm.value?.dirty)||uncertain.value),router)
const invalid=computed(()=>!reason.value.trim()||!validNumber(total.value)||lines.value.some(line=>!line.specialty_id||!validNumber(line.count))||new Set(lines.value.map(line=>line.specialty_id)).size!==lines.value.length||
 balance.value!==null&&balance.value<0||(number(total.value)!==null||lines.value.some(line=>number(line.count)!==null))&&!basis.value.trim()&&documentMode.value==='existing'&&!documentId.value.trim())
const show=(value:unknown)=>value==null||value===''?'Неизвестно':String(value)
const labels={year:'Год',total:'Общий годовой план',basis_text:'Основание плана',document_id:'Документ',version:'Редакция',lines:'Планы специальностей'}
function historyValue(key:string,value:unknown){return key==='lines'?Array.isArray(value)&&value.length?value.map(line=>`${line.specialty.code} · ${line.specialty.name}: ${show(line.count)}`).join('\n'):'Распределение не задано':show(value)}
async function refresh(){
 loading.value=true;loadError.value=null
 try{await requests.run(signal=>api.request<StateAssignmentPlan>(`/report-plans/${props.year}/`,{signal}),value=>{current.value=value;loading.value=false})}
 catch(cause){loadError.value=cause;loading.value=false}
}
function start(){
 if(!current.value||!canEdit.value)return
 total.value=current.value.total===null?'':String(current.value.total);basis.value=current.value.basis_text;documentId.value=current.value.document_id??'';documentMode.value='existing';reason.value='';expectedVersion.value=current.value.version
 lines.value=current.value.lines.map(line=>({key:++sequence,specialty_id:line.specialty.id,count:line.count===null?'':String(line.count)}));reset();editing.value=true;initial.value=stamp.value
}
function acceptVersion(){if(current.value&&canEdit.value){expectedVersion.value=current.value.version;reset()}}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave()){editing.value=false;reset()}}
function submit(){if(uncertain.value||canEdit.value&&!invalid.value&&!conflict.value&&!documentForm.value?.uploadConflict&&!loading.value&&!loadError.value)void command.submit()}
onMounted(()=>void refresh());onBeforeUnmount(()=>requests.cancel())
</script>
<template>
 <ApiMessage :error="loadError"/><p v-if="loading" class="state" role="status">Загрузка плана {{year}}…</p><button v-if="loadError" @click="refresh">Повторить загрузку плана</button>
 <section v-if="current" class="card plan-card"><div class="section-heading"><div><p class="eyebrow">{{year}} · {{current.id?`редакция ${current.version}`:'План ещё не задан'}}</p><h2>План госзадания</h2></div><div class="button-row"><button data-plan-refresh :disabled="busy||loading" @click="refresh">Обновить серверные сведения</button><button v-if="canEdit&&!editing" data-plan-edit class="button-primary" @click="start">{{current.id?'Изменить план':'Задать план'}}</button></div></div>
  <p class="muted">Пустое значение — неизвестно, а не ноль. Общий итог не восстанавливается из неполной разбивки. Изменение плана требует пересчитать15.1 перед скачиванием.</p>
  <div class="plan-totals"><div><small>Общий годовой план</small><strong>{{show(current.total)}}</strong></div><div><small>Известная сумма специальностей</small><strong>{{currentKnownSum}}</strong></div><div><small>Не распределено в известных строках</small><strong>{{current.total===null?'Неизвестно':current.total-currentKnownSum}}</strong></div></div><p class="muted">Строк с неизвестным значением: {{current.lines.filter(line=>line.count===null).length}}. Отсутствующая строка также не подтверждает нулевой план.</p>
  <p>{{current.basis_text||'Основание не указано'}}</p><BasisPreview v-if="current.document" :document="current.document" heading="Документ плана"/>
  <div data-plan-lines class="table-scroll"><table><thead><tr><th>Специальность</th><th>Годовой объём</th></tr></thead><tbody><tr v-for="line in current.lines" :key="line.id"><td>{{line.specialty.code}} · {{line.specialty.name}}</td><td>{{show(line.count)}}</td></tr></tbody></table><p v-if="!current.lines.length" class="muted">Разбивка по специальностям не задана. Отсутствующие строки не считаются нулевыми.</p></div>
  <p v-if="!canEdit" class="muted">Только просмотр. Изменение требует отдельного права «Вести годовые планы госзадания» по учреждению.</p>
  <form v-if="editing" data-plan-form class="inset-form form-grid" @submit.prevent="submit"><ApiMessage :error="error"/>
   <p v-if="uncertain" class="message">Ответ не получен. Повтор отправит ту же попытку с тем же годом, вводом и документом.</p><p v-if="!canEdit" class="message message-error">Право изменения недоступно. Ввод сохранён.</p>
   <p v-if="conflict&&!uncertain" class="message">План изменился. Обновите серверные сведения; ввод останется. <button v-if="current.version!==expectedVersion&&canEdit" data-plan-accept-version type="button" @click="acceptVersion">Принять редакцию {{current.version}} для новой попытки</button></p>
   <fieldset data-plan-fields class="form-grid" :disabled="busy||uncertain||!canEdit||loading">
    <label>Общий годовой план (пусто — неизвестно)<input v-model="total" name="plan_total" type="number" min="0" max="2147483647" step="1"/></label>
    <article v-for="(line,index) in lines" :key="line.key" class="plan-line form-grid"><div class="section-heading"><h3>Специальность {{index+1}}</h3><button data-plan-remove-line type="button" @click="lines.splice(index,1)">Убрать строку</button></div><label>Специальность<select v-model="line.specialty_id" name="plan_specialty_id" required><option value="">Выберите специальность</option><option v-for="specialty in choices" :key="specialty.id" :value="specialty.id">{{specialty.code}} · {{specialty.name}}{{specialty.is_active?'':' (неактивна, использовалась)'}}</option></select></label><label>Годовой объём (пусто — неизвестно)<input v-model="line.count" name="plan_count" type="number" min="0" max="2147483647" step="1"/></label></article>
    <button data-plan-add-line type="button" :disabled="lines.length>=1000" @click="lines.push({key:++sequence,specialty_id:'',count:''})">Добавить специальность</button><p data-plan-balance class="message">Сумма известных строк: {{knownSum}} · Не распределено в известных строках: {{balance===null?'Неизвестно':balance}}. Остальные значения не подставляются автоматически.</p>
    <label>Основание и реквизиты плана<textarea v-model="basis" name="plan_basis_text" maxlength="100000" rows="3"/></label><label>Документ (необязательно при текстовом основании)<select v-model="documentMode" name="plan_document_mode"><option value="existing">Без файла или существующий документ по ID</option><option v-if="session.can('documents.upload')" value="new">Подкрепить новый документ</option></select></label><label v-if="documentMode==='existing'">ID существующего документа<input v-model="documentId" name="plan_document_id"/></label>
    <BasisDocumentForm v-else ref="documentForm" department-id="" :busy="busy||uncertain" :kind-options="[{value:'letter',label:'Документ утверждения плана'}]" heading="Документ годового плана" saved-note="План сохраняется отдельно." @changed="reset"/>
    <label>Основание изменения<textarea v-model="reason" name="plan_reason" maxlength="100000" rows="2" required/></label>
   </fieldset><div class="button-row"><button data-plan-submit class="button-primary" :disabled="busy||!uncertain&&(invalid||conflict||documentForm?.uploadConflict||loading||!!loadError||!canEdit)" :formnovalidate="uncertain">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить годовой план'}}</button><button type="button" :disabled="busy||uncertain" @click="cancel">Отмена</button></div>
  </form><FactHistory :revisions="current.revisions" :labels="labels" :format-value="historyValue"/>
 </section>
</template>
<style scoped>.plan-card{margin-top:20px}.plan-totals{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:24px 0}.plan-totals strong{display:block;font-size:30px;margin-top:8px}.plan-line{padding:18px;border:1px solid var(--border);border-radius:12px;background:var(--surface,#fff)}@media(max-width:850px){.plan-totals{grid-template-columns:1fr}}</style>
