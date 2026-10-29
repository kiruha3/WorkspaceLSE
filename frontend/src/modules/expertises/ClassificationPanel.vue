<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import type { ClassificationOptions,ClassificationPayload,Expertise,ExpertiseCommandResponse,PreviousConclusionPayload } from '../../api/types'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useCommandAttempt,type CommandPacket } from '../../shared/ui/useCommandAttempt'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import DocumentPicker from '../../shared/DocumentPicker.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import FactHistory from '../../shared/FactHistory.vue'
const props=defineProps<{expertise:Expertise}>(),emit=defineEmits<{updated:[Expertise]}>()
const api=useApi(),router=useRouter(),requests=new LatestRequest()
const details=computed(()=>props.expertise.classification!),editing=ref(false),loading=ref(false),optionsError=ref<unknown>(null),options=ref<ClassificationOptions|null>(null)
const nature=ref(''),complete=ref(false),reason=ref(''),expectedVersion=ref(0),initial=ref('')
type Entry={key:string;reference:string;organization_name:string;organization_group:string;same_input_data:string;confirms_previous:string;document_id:string;documentMode:string}
const entries=ref<Entry[]>([]),documentForms=new Map<string,InstanceType<typeof DocumentPicker>>()
let sequence=0,preparation:{packet:CommandPacket;newDocuments:{key:string;index:number}[]}|null=null
const natureLabels:Record<string,string>={primary:'Первичная',repeated:'Повторная',additional:'Дополнительная'}
const groupLabels:Record<string,string>={ministry:'ФБУ СЭУ Минюста России',other_state:'Иные государственные СЭУ России',other:'Иные учреждения, организации и частные эксперты'}
const labels={appointment_nature:'Характер назначения',previous_complete:'Полнота списка прежних заключений',previous_conclusions:'Предыдущие заключения',department_code:'Фактический отдел',registration_department_code:'Код отдела в номере'}
const flag=(value:string)=>value===''?null:value==='true'
const flagText=(value:unknown)=>value===null||value===undefined?'Неизвестно':value?'Да':'Нет'
function historyValue(key:string,value:unknown):string{
 if(key==='appointment_nature')return natureLabels[String(value)]??'Не уточнён'
 if(key==='previous_conclusions')return Array.isArray(value)&&value.length?value.map((item:PreviousConclusionPayload,index:number)=>`${index+1}. ${item.reference}\nУчреждение: ${item.organization_name||'Неизвестно'}\nГруппа: ${groupLabels[item.organization_group??'']??'Неизвестно'}\nТе же исходные данные: ${flagText(item.same_input_data)}\nВыводы подтверждены: ${flagText(item.confirms_previous)}\nДокумент: ${item.document_id||'Не подкреплён'}`).join('\n\n'):'Список пуст / не заполнен'
 if(value==null||value==='')return 'Неизвестно'
 return typeof value==='boolean'?flagText(value):String(value)
}
const payload=computed<ClassificationPayload>(()=>({expected_version:expectedVersion.value,reason:reason.value.trim(),appointment_nature:(nature.value||null) as Expertise['appointment_nature'],previous_complete:complete.value,previous_conclusions:entries.value.map(e=>({reference:e.reference.trim(),organization_name:e.organization_name.trim(),organization_group:(e.organization_group||null) as PreviousConclusionPayload['organization_group'],same_input_data:flag(e.same_input_data),confirms_previous:flag(e.confirms_previous),document_id:e.document_id.trim()||null}))}))
const stamp=computed(()=>JSON.stringify([payload.value,entries.value.map(e=>[e.key,e.documentMode])]))
const command=useCommandAttempt<ExpertiseCommandResponse>(async()=>{
 if(!preparation)preparation={packet:{path:`/expertises/${props.expertise.id}/classification/`,method:'POST',body:JSON.parse(JSON.stringify(payload.value))},newDocuments:entries.value.flatMap((e,index)=>e.documentMode==='new'?[{key:e.key,index}]:[])}
 const plan=preparation,body=plan.packet.body as ClassificationPayload
 for(const item of plan.newDocuments){const form=documentForms.get(item.key);if(!form)throw new ApiError(400,'validation_error','Форма предыдущего заключения недоступна.');body.previous_conclusions[item.index]!.document_id=(await form.persist()).id}
 return plan.packet
},response=>{editing.value=false;preparation=null;emit('updated',response.expertise)})
const {busy,uncertain,error,conflict}=command
const confirmLeave=useDirtyGuard(()=>busy.value||editing.value&&(stamp.value!==initial.value||[...documentForms.values()].some(f=>f.dirty)||uncertain.value),router)
function reset(){if(!busy.value&&!uncertain.value){preparation=null;command.reset()}}
watch(stamp,reset,{flush:'sync'})
const invalid=computed(()=>!reason.value.trim()||props.expertise.origin_kind==='native'&&!nature.value||entries.value.some(e=>!e.reference.trim())||complete.value&&['repeated','additional'].includes(nature.value)&&!entries.value.length)
async function loadOptions(){loading.value=true;optionsError.value=null;try{await requests.run(signal=>api.request<ClassificationOptions>(`/expertises/${props.expertise.id}/classification/`,{signal}),value=>{options.value=value;loading.value=false})}catch(cause){optionsError.value=cause;loading.value=false}}
async function start(){
 nature.value=props.expertise.appointment_nature??'';complete.value=details.value.previous_complete;reason.value='';expectedVersion.value=props.expertise.version
 entries.value=details.value.previous_conclusions.map(e=>({key:String(++sequence),reference:e.reference,organization_name:e.organization_name,organization_group:e.organization_group??'',same_input_data:e.same_input_data===null?'':String(e.same_input_data),confirms_previous:e.confirms_previous===null?'':String(e.confirms_previous),document_id:e.document_id??'',documentMode:'existing'}))
 reset();editing.value=true;initial.value=stamp.value;await loadOptions()
}
function add(){if(entries.value.length<100)entries.value.push({key:String(++sequence),reference:'',organization_name:'',organization_group:'',same_input_data:'',confirms_previous:'',document_id:'',documentMode:'existing'})}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave()){editing.value=false;requests.cancel();reset()}}
function acceptVersion(){expectedVersion.value=props.expertise.version;reset()}
function submit(){if(uncertain.value||details.value.can_edit&&!invalid.value&&!conflict.value&&!loading.value&&!optionsError.value)void command.submit()}
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
 <section data-classification-panel class="card stack-card"><div class="section-heading"><div><p class="eyebrow">Классификация работы · раздел 4 формы 15.1</p><h2>Характер назначения и предыдущие заключения</h2></div><button v-if="details.can_edit&&!editing" data-classification-edit @click="start">Уточнить характер назначения</button></div>
  <dl class="work-facts"><div><dt>Характер назначения</dt><dd>{{natureLabels[expertise.appointment_nature??'']||'Не уточнён'}}</dd></div><div><dt>Полнота списка прежних заключений</dt><dd>{{details.previous_complete?'Подтверждена':'Не подтверждена'}}</dd></div></dl>
  <p class="muted compact">Первичная, дополнительная или повторная — независимо от комиссии и комплекса. Изменение не меняет номер, отдел, исполнителей, принятый результат или выдачу.</p>
  <article v-for="(entry,index) in details.previous_conclusions" :key="entry.id" class="previous-summary"><h3>{{index+1}}. {{entry.reference}}</h3><dl class="work-facts"><div><dt>Прежнее учреждение</dt><dd>{{entry.organization_name||'Неизвестно'}} · {{groupLabels[entry.organization_group??'']||'Группа неизвестна'}}</dd></div><div><dt>Те же исходные данные</dt><dd>{{flagText(entry.same_input_data)}}</dd></div><div><dt>Выводы подтверждены</dt><dd>{{flagText(entry.confirms_previous)}}</dd></div></dl><BasisPreview v-if="entry.document" :document="entry.document" heading="Предыдущее заключение"/></article>
  <p v-if="!details.previous_conclusions.length" class="muted">Предыдущие заключения не указаны. Это не подтверждает первичность работы.</p>
  <form v-if="editing" data-classification-form class="inset-form form-grid" @submit.prevent="submit"><ApiMessage :error="error"/><ApiMessage :error="optionsError"/><p v-if="loading" role="status">Загрузка групп учреждений…</p><button v-if="optionsError" type="button" @click="loadOptions">Повторить загрузку групп</button>
   <p v-if="uncertain" class="message">Ответ не получен. Повтор отправит ту же попытку с теми же документами.</p><p v-if="!details.can_edit" class="message message-error">Право изменения недоступно. Ввод сохранён.</p>
   <p v-if="conflict&&!uncertain" class="message">Карточка изменилась. Обновите серверные сведения; ввод останется. <button v-if="expectedVersion!==expertise.version" data-classification-accept-version type="button" @click="acceptVersion">Принять версию {{expertise.version}} для новой попытки</button></p>
   <fieldset data-classification-fields class="form-grid" :disabled="busy||uncertain||!details.can_edit||loading">
    <label>Характер назначения<select v-model="nature" name="classification_nature"><option v-if="expertise.origin_kind==='historical'" value="">Не уточнён</option><option v-for="(label,key) in natureLabels" :key="key" :value="key">{{label}}</option></select></label>
    <article v-for="(entry,index) in entries" :key="entry.key" class="previous-editor form-grid"><div class="section-heading"><h3>Предыдущее заключение {{index+1}}</h3><button data-remove-previous type="button" @click="entries.splice(index,1)">Убрать из текущего списка</button></div>
     <label>Известные реквизиты предыдущего заключения<input v-model="entry.reference" name="previous_reference" maxlength="500" required/></label>
     <div class="form-columns"><label>Название прежнего учреждения<input v-model="entry.organization_name" name="previous_organization_name" maxlength="500"/></label><label>Группа прежнего учреждения<select v-model="entry.organization_group" name="previous_organization_group"><option value="">Неизвестно</option><option v-for="group in options?.organization_groups" :key="group.code" :value="group.code">{{group.name}}</option></select></label></div>
     <div class="form-columns"><label>Исследование по тем же исходным данным<select v-model="entry.same_input_data" name="previous_same_input_data"><option value="">Неизвестно</option><option value="true">Да</option><option value="false">Нет</option></select></label><label>Прежние выводы подтверждены<select v-model="entry.confirms_previous" name="previous_confirms"><option value="">Неизвестно</option><option value="true">Да</option><option value="false">Нет</option></select></label></div>
     <DocumentPicker :ref="el=>{if(el)documentForms.set(entry.key,el as InstanceType<typeof DocumentPicker>);else documentForms.delete(entry.key)}" v-model="entry.document_id" v-model:mode="entry.documentMode" name="previous_document_id" :document="details.previous_conclusions.find(item=>item.document_id===entry.document_id)?.document" :department-id="expertise.department.id" :busy="busy||uncertain" :kind-options="[{value:'expert_conclusion',label:'Предыдущее заключение эксперта'}]" heading="Предыдущее заключение (необязательно)" saved-note="Связь с работой сохраняется отдельной командой." @changed="reset"/>
    </article>
    <button data-add-previous type="button" :disabled="entries.length>=100" @click="add">Добавить предыдущее заключение</button>
    <label class="check-line"><input v-model="complete" name="previous_complete" type="checkbox"/>Подтверждаю, что список предыдущих заключений полон</label>
    <p class="muted compact">Полнота списка и известность каждого поля — разные сведения. «Не подтвердились выводы» учитывается только при тех же исходных данных и явном «Нет». СНДЗ не означает автоматически неподтверждение.</p>
    <label>Основание изменения<textarea v-model="reason" name="classification_reason" rows="2" required/></label>
   </fieldset><div class="button-row"><button data-classification-submit class="button-primary" :disabled="busy||!uncertain&&(invalid||conflict||loading||!!optionsError||!details.can_edit)" :formnovalidate="uncertain">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить классификацию'}}</button><button type="button" :disabled="busy||uncertain" @click="cancel">Отмена</button></div>
  </form><FactHistory :revisions="details.revisions" :labels="labels" :format-value="historyValue"/>
 </section>
</template>
<style scoped>.previous-summary,.previous-editor{border-top:1px solid var(--border);padding-top:18px;margin-top:12px}.previous-editor{background:var(--surface,#fff);padding:18px;border:1px solid var(--border);border-radius:12px}dd{white-space:pre-wrap;overflow-wrap:anywhere}.check-line{display:flex;gap:10px;align-items:center}.check-line input{width:18px;height:18px;flex-shrink:0}</style>
