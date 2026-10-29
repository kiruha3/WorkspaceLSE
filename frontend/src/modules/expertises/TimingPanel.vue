<script setup lang="ts">
import { computed,onBeforeUnmount,ref,shallowReactive,watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import type { DocumentKind,Expertise,ExpertiseCommandResponse,TimingOptions,TimingPayload } from '../../api/types'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useCommandAttempt,type CommandPacket } from '../../shared/ui/useCommandAttempt'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import DocumentPicker from '../../shared/DocumentPicker.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import FactHistory from '../../shared/FactHistory.vue'
const props=defineProps<{expertise:Expertise}>(),emit=defineEmits<{updated:[Expertise]}>()
const api=useApi(),router=useRouter(),requests=new LatestRequest()
const details=computed(()=>props.expertise.timing!),editing=ref(false),loading=ref(false),optionsError=ref<unknown>(null),options=ref<TimingOptions|null>(null)
type Flag='notification_sent'|'extension_requested'|'deadline_breached'
type Slot='notification'|'request'|'breach'
const slots:{key:Slot;flag:Flag;date:'notification_on'|'request_on'|null;label:string;kind:DocumentKind}[]=[
 {key:'notification',flag:'notification_sent',date:'notification_on',label:'Фактическое информирование о невозможности исполнить в установленный срок',kind:'notification'},
 {key:'request',flag:'extension_requested',date:'request_on',label:'Фактически направленное ходатайство о продлении',kind:'deadline_request'},
 {key:'breach',flag:'deadline_breached',date:null,label:'Подтверждённое нарушение установленного / согласованного срока',kind:'deadline_agreement'},
]
const flags=ref<Record<Flag,string>>({notification_sent:'',extension_requested:'',deadline_breached:''}),dates=ref({notification_on:'',request_on:''})
const documents=ref<Record<Slot,{id:string;mode:string}>>({notification:{id:'',mode:'existing'},request:{id:'',mode:'existing'},breach:{id:'',mode:'existing'}})
type Entry={key:string;reason_id:string;comment:string;document_id:string;documentMode:string}
const entries=ref<Entry[]>([]),complete=ref(false),primary=ref(''),basis=ref(''),reason=ref(''),expectedVersion=ref(0),initial=ref('')
const documentForms=shallowReactive(new Map<string,InstanceType<typeof DocumentPicker>>())
const documentConflict=computed(()=>[...documentForms.values()].some(form=>form.uploadConflict))
let sequence=0,preparation:{packet:CommandPacket;documents:{key:string;field?:string;index?:number}[]}|null=null
const bool=(value:string)=>value===''?null:value==='true',show=(value:unknown)=>value==null||value===''?'Неизвестно':typeof value==='boolean'?value?'Да':'Нет':String(value)
const labels={reasons:'Причины длительности',reasons_complete:'Полнота списка причин',primary_reason_id:'Основная причина',notification_sent:'Факт информирования',notification_on:'Дата информирования',notification_document_id:'Документ информирования',extension_requested:'Факт направления ходатайства',request_on:'Дата ходатайства',request_document_id:'Документ ходатайства',deadline_breached:'Оценка нарушения срока',breach_basis:'Основание оценки',breach_document_id:'Документ оценки'}
function historyValue(key:string,value:unknown){
 if(key==='reasons')return Array.isArray(value)&&value.length?value.map((item,index)=>`${index+1}. ${item.reason.name}\n${item.comment||'Без пояснения'}\nДокумент: ${item.document_id||'Не подкреплён'}`).join('\n\n'):'Список пуст / не заполнен'
 return show(value)
}
const reasonOptions=computed(()=>options.value?.delay_reasons.filter(r=>r.is_active||options.value?.retained_reason_ids.includes(r.id))??[])
const primaryOptions=computed(()=>reasonOptions.value.filter(r=>entries.value.some(e=>e.reason_id===r.id)))
watch(()=>entries.value.map(e=>e.reason_id),ids=>{if(primary.value&&!ids.includes(primary.value))primary.value=''},{flush:'sync'})
const payload=computed<TimingPayload>(()=>({expected_version:expectedVersion.value,reason:reason.value.trim(),reasons_complete:complete.value,primary_reason_id:primary.value||null,reasons:entries.value.map(e=>({reason_id:e.reason_id,comment:e.comment.trim(),document_id:e.document_id.trim()||null})),
 notification_sent:bool(flags.value.notification_sent),notification_on:flags.value.notification_sent==='false'?null:dates.value.notification_on||null,notification_document_id:flags.value.notification_sent==='false'?null:documents.value.notification.id.trim()||null,
 extension_requested:bool(flags.value.extension_requested),request_on:flags.value.extension_requested==='false'?null:dates.value.request_on||null,request_document_id:flags.value.extension_requested==='false'?null:documents.value.request.id.trim()||null,
 deadline_breached:bool(flags.value.deadline_breached),breach_basis:basis.value.trim(),breach_document_id:documents.value.breach.id.trim()||null}))
const stamp=computed(()=>JSON.stringify([payload.value,documents.value,entries.value.map(e=>[e.key,e.documentMode])]))
const command=useCommandAttempt<ExpertiseCommandResponse>(async()=>{
 if(!preparation)preparation={packet:{path:`/expertises/${props.expertise.id}/timing/`,method:'POST',body:JSON.parse(JSON.stringify(payload.value))},documents:[
  ...slots.flatMap(s=>documents.value[s.key].mode==='new'&&(s.key==='breach'||flags.value[s.flag]!=='false')?[{key:s.key,field:`${s.key}_document_id`}]:[]),
  ...entries.value.flatMap((e,index)=>e.documentMode==='new'?[{key:`reason-${e.key}`,index}]:[])]}
 const plan=preparation,body=plan.packet.body as TimingPayload
 for(const item of plan.documents){const form=documentForms.get(item.key);if(!form)throw new ApiError(400,'validation_error','Форма подтверждающего документа недоступна.');const doc=await form.persist();if(item.index!==undefined)body.reasons[item.index]!.document_id=doc.id;else (body as unknown as Record<string,unknown>)[item.field!]=doc.id}
 return plan.packet
},response=>{editing.value=false;preparation=null;emit('updated',response.expertise)})
const {busy,uncertain,error}=command
const conflict=computed(()=>command.conflict.value&&!(error.value instanceof ApiError&&error.value.code==='document_version_conflict'))
const confirmLeave=useDirtyGuard(()=>busy.value||editing.value&&(stamp.value!==initial.value||[...documentForms.values()].some(f=>f.dirty)||uncertain.value),router)
function reset(){if(!busy.value&&!uncertain.value){preparation=null;command.reset()}}
watch(stamp,reset,{flush:'sync'})
const invalid=computed(()=>!reason.value.trim()||entries.value.some(e=>!e.reason_id)||new Set(entries.value.map(e=>e.reason_id)).size!==entries.value.length||
 slots.some(s=>(s.key==='breach'?flags.value[s.flag]!=='':flags.value[s.flag]==='true')&&(documents.value[s.key].mode==='existing'&&!documents.value[s.key].id.trim()||s.key==='breach'&&!basis.value.trim())))
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Krasnoyarsk',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
async function loadOptions(){loading.value=true;optionsError.value=null;try{await requests.run(signal=>api.request<TimingOptions>(`/expertises/${props.expertise.id}/timing/`,{signal}),value=>{options.value=value;loading.value=false})}catch(cause){optionsError.value=cause;loading.value=false}}
async function start(){
 for(const s of slots){flags.value[s.flag]=details.value[s.flag]===null?'':String(details.value[s.flag]);documents.value[s.key]={id:details.value[`${s.key}_document_id`]??'',mode:'existing'}}
 dates.value={notification_on:details.value.notification_on??'',request_on:details.value.request_on??''};basis.value=details.value.breach_basis;complete.value=details.value.reasons_complete;primary.value=details.value.primary_reason_id??''
 entries.value=details.value.reasons.map(e=>({key:String(++sequence),reason_id:e.reason.id,comment:e.comment,document_id:e.document_id??'',documentMode:'existing'}));primary.value=details.value.primary_reason_id??''
 reason.value='';expectedVersion.value=props.expertise.version;reset();editing.value=true;initial.value=stamp.value;await loadOptions()
}
function add(){if(entries.value.length<100)entries.value.push({key:String(++sequence),reason_id:'',comment:'',document_id:'',documentMode:'existing'})}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave()){editing.value=false;requests.cancel();reset()}}
function acceptVersion(){expectedVersion.value=props.expertise.version;reset()}
function submit(){if(uncertain.value||details.value.can_edit&&!invalid.value&&!conflict.value&&!documentConflict.value&&!loading.value&&!optionsError.value)void command.submit()}
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
 <section data-timing-panel class="card stack-card"><div class="section-heading"><div><p class="eyebrow">Раздел 3 формы 15.1 · подтверждённые факты</p><h2>Причины длительности и подтверждения срока</h2></div><button v-if="details.can_edit&&!editing" data-timing-edit @click="start">Уточнить сведения о сроках</button></div>
  <p class="muted compact">Запись факта не отправляет письмо, не продлевает срок и не меняет окончание работы. Исходный, запрошенный и согласованный сроки остаются в событиях производства. Календарные дни не подменяют юридическую оценку.</p>
  <dl class="work-facts"><div><dt>Полнота списка причин</dt><dd>{{details.reasons_complete?'Подтверждена':'Не подтверждена'}}</dd></div><div><dt>Основная причина</dt><dd>{{details.reasons.find(e=>e.reason.id===details.primary_reason_id)?.reason.name||'Не указана'}}</dd></div></dl>
  <article v-for="entry in details.reasons" :key="entry.id" class="timing-item"><h3>{{entry.reason.name}}</h3><p>{{entry.comment||'Пояснение не указано'}}</p><BasisPreview v-if="entry.document" :document="entry.document" heading="Подтверждение причины"/></article><p v-if="!details.reasons.length" class="muted">Причины не уточнены. Загруженность и «иные» автоматически не выбираются.</p>
  <article v-for="slot in slots" :key="slot.key" class="timing-item"><h3>{{slot.label}}</h3><p>{{show(details[slot.flag])}}<template v-if="slot.date"> · дата: {{details[slot.date]||'Неизвестна'}}</template></p><p v-if="slot.key==='breach'&&details.breach_basis">{{details.breach_basis}}</p><BasisPreview v-if="details[`${slot.key}_document`]" :document="details[`${slot.key}_document`]" heading="Документ подтверждения"/></article>
  <form v-if="editing" data-timing-form class="inset-form form-grid" @submit.prevent="submit"><ApiMessage :error="error"/><ApiMessage :error="optionsError"/><p v-if="loading" role="status">Загрузка причин…</p><button v-if="optionsError" type="button" @click="loadOptions">Повторить загрузку причин</button>
   <p v-if="uncertain" class="message">Ответ не получен. Повтор отправит ту же попытку с теми же документами.</p><p v-if="!details.can_edit" class="message message-error">Право изменения недоступно. Ввод сохранён.</p><p v-if="conflict&&!uncertain" class="message">Карточка изменилась. Обновите серверные сведения; ввод останется. <button v-if="expectedVersion!==expertise.version" data-timing-accept-version type="button" @click="acceptVersion">Принять версию {{expertise.version}} для новой попытки</button></p>
   <fieldset data-timing-fields class="form-grid" :disabled="busy||uncertain||!details.can_edit||loading">
    <h3>Причины срока свыше 30 календарных дней</h3><p class="muted compact">{{options?.delay_reason_policy==='all'?'Одна работа учитывается в каждой выбранной группе причин.':options?.delay_reason_policy==='primary'?'Отчёт учитывает только основную причину.':'Правило нескольких причин пока не подтверждено. Сохраните фактический набор и основную причину, если она установлена; неоднозначный итог останется неизвестным.'}}</p>
    <article v-for="(entry,index) in entries" :key="entry.key" class="timing-editor form-grid"><div class="section-heading"><h4>Причина {{index+1}}</h4><button data-remove-timing-reason type="button" @click="entries.splice(index,1)">Убрать причину</button></div>
     <label>Причина длительности<select v-model="entry.reason_id" name="timing_delay_reason_id" required><option value="">Выберите известную причину</option><option v-for="r in reasonOptions" :key="r.id" :value="r.id">{{r.name}}{{r.is_active?'':' (неактивна, использовалась)'}}</option></select></label><label>Пояснение<textarea v-model="entry.comment" name="timing_delay_comment" rows="2" maxlength="100000"/></label>
     <DocumentPicker :ref="el=>{if(el)documentForms.set(`reason-${entry.key}`,el as InstanceType<typeof DocumentPicker>);else documentForms.delete(`reason-${entry.key}`)}" v-model="entry.document_id" v-model:mode="entry.documentMode" name="timing_reason_document_id" :document="details.reasons.find(item=>item.document_id===entry.document_id)?.document" :department-id="expertise.department.id" :busy="busy||uncertain" :kind-options="[{value:'letter',label:'Документ подтверждения причины'}]" heading="Подтверждение причины (необязательно)" saved-note="Сведения о сроках сохраняются отдельно." @changed="reset"/>
    </article><button data-add-timing-reason type="button" :disabled="entries.length>=100" @click="add">Добавить причину</button>
    <label>Основная причина (если установлена)<select v-model="primary" name="timing_primary_reason"><option value="">Не указана</option><option v-for="r in primaryOptions" :key="r.id" :value="r.id">{{r.name}}</option></select></label><label class="check-line"><input v-model="complete" name="timing_reasons_complete" type="checkbox"/>Подтверждаю полноту списка причин</label>
    <section v-for="slot in slots" :key="slot.key" class="timing-editor form-grid"><h3>{{slot.label}}</h3><label>Подтверждённый факт<select v-model="flags[slot.flag]" :name="`timing_${slot.flag}`"><option value="">Неизвестно</option><option value="true">Да</option><option value="false">Нет</option></select></label>
     <template v-if="slot.key==='breach'||flags[slot.flag]!=='false'"><label v-if="slot.date">Фактическая дата (может быть неизвестна)<input v-model="dates[slot.date]" :name="`timing_${slot.date}`" type="date" :min="expertise.receipt.received_at" :max="today()"/></label><label v-if="slot.key==='breach'">Основание оценки срока<textarea v-model="basis" name="timing_breach_basis" rows="2" :required="flags.deadline_breached!==''"/></label>
      <DocumentPicker :ref="el=>{if(el)documentForms.set(slot.key,el as InstanceType<typeof DocumentPicker>);else documentForms.delete(slot.key)}" v-model="documents[slot.key].id" v-model:mode="documents[slot.key].mode" :name="`timing_${slot.key}_document_id`" :document="details[`${slot.key}_document`]" :department-id="expertise.department.id" :busy="busy||uncertain" :kind-options="[{value:slot.kind,label:'Документ подтверждения'}]" heading="Документ подтверждения" saved-note="Сведения о сроках сохраняются отдельно." @changed="reset"/>
     </template><p class="muted compact">{{slot.key==='breach'?'Для известного «да» или «нет» нужны основание и документ. Отсутствие согласования само по себе не подставляет оценку.':'«Да» требует документа. Неизвестную дату не выдумывайте: графа информирования останется предварительной. Запись запроса или черновик письма не означает отправку.'}}</p>
    </section><label>Основание изменения<textarea v-model="reason" name="timing_reason" rows="2" required/></label>
   </fieldset><div class="button-row"><button data-timing-submit class="button-primary" :disabled="busy||!uncertain&&(invalid||conflict||documentConflict||loading||!!optionsError||!details.can_edit)" :formnovalidate="uncertain">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить сведения о сроках'}}</button><button type="button" :disabled="busy||uncertain" @click="cancel">Отмена</button></div>
  </form><FactHistory :revisions="details.revisions" :labels="labels" :format-value="historyValue"/>
 </section>
</template>
<style scoped>.timing-item{border-top:1px solid var(--border);padding-top:18px;margin-top:14px}.timing-editor{padding:18px;border:1px solid var(--border);border-radius:12px;background:var(--surface,#fff)}dd{white-space:pre-wrap;overflow-wrap:anywhere}.check-line{display:flex;gap:10px;align-items:center}.check-line input{width:18px;height:18px;flex-shrink:0}</style>
