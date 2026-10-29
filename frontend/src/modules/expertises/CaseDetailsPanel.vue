<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import type { CaseDetailsOptions,CaseDetailsPayload,Expertise,ExpertiseCommandResponse } from '../../api/types'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useCommandAttempt,type CommandPacket } from '../../shared/ui/useCommandAttempt'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import DocumentPicker from '../../shared/DocumentPicker.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import FactHistory from '../../shared/FactHistory.vue'
import { caseFields,caseLabels } from '../references/catalogs'
const props=defineProps<{expertise:Expertise}>(),emit=defineEmits<{updated:[Expertise]}>()
const api=useApi(),router=useRouter(),requests=new LatestRequest()
const details=computed(()=>props.expertise.case_details!),editing=ref(false),loading=ref(false),optionsError=ref<unknown>(null),options=ref<CaseDetailsOptions|null>(null)
const constructionEligible=computed(()=>['16.1','16.2'].includes(props.expertise.specialty?.code??''))
const text=ref(Object.fromEntries(caseFields.map(([key])=>[key,''])) as Record<typeof caseFields[number][0],string>)
const authority=ref(''),decree=ref(''),basis=ref(''),documentId=ref(''),documentMode=ref('existing'),reason=ref(''),expectedVersion=ref(0),initial=ref('')
const documentForm=ref<InstanceType<typeof DocumentPicker>|null>(null)
let preparation:{packet:CommandPacket;newDocument:boolean}|null=null
const payload=computed<CaseDetailsPayload>(()=>({...text.value,expected_version:expectedVersion.value,reason:reason.value.trim(),authority_type_id:authority.value||null,decree3214:decree.value===''?null:decree.value==='true',decree_document_id:decree.value==='true'?documentId.value||null:null,decree_basis:decree.value==='true'?basis.value.trim():''}))
const stamp=computed(()=>JSON.stringify([payload.value,documentMode.value]))
const command=useCommandAttempt<ExpertiseCommandResponse>(async()=>{
 if(!preparation)preparation={packet:{path:`/expertises/${props.expertise.id}/case-details/`,method:'POST',body:JSON.parse(JSON.stringify(payload.value))},newDocument:decree.value==='true'&&documentMode.value==='new'}
 const plan=preparation,body=plan.packet.body as CaseDetailsPayload
 if(plan.newDocument){if(!documentForm.value)throw new ApiError(400,'validation_error','Форма документа недоступна.');body.decree_document_id=(await documentForm.value.persist()).id}
 return plan.packet
},response=>{editing.value=false;preparation=null;emit('updated',response.expertise)})
const {busy,uncertain,error,conflict}=command
const confirmLeave=useDirtyGuard(()=>busy.value||editing.value&&(stamp.value!==initial.value||Boolean(documentForm.value?.dirty)||uncertain.value),router)
function reset(){if(!busy.value&&!uncertain.value){preparation=null;command.reset()}}
watch(stamp,reset,{flush:'sync'})
const types=computed(()=>options.value?.authority_types.filter(item=>item.is_active||options.value?.retained_authority_type_ids.includes(item.id))??[])
const invalid=computed(()=>!reason.value.trim())
function toggleConstruction(event:Event){decree.value=(event.target as HTMLInputElement).checked?'true':'false'}
async function loadOptions(){loading.value=true;optionsError.value=null;try{await requests.run(signal=>api.request<CaseDetailsOptions>(`/expertises/${props.expertise.id}/case-details/`,{signal}),value=>{options.value=value;if(details.value.source!=='typed')authority.value=value.initial_authority_type_id??'';loading.value=false;initial.value=stamp.value})}catch(cause){optionsError.value=cause;loading.value=false}}
async function start(){
 for(const [field] of caseFields)text.value[field]=details.value[field]
 authority.value=details.value.authority_type?.id??'';decree.value=details.value.decree3214===null?'':String(details.value.decree3214);basis.value=details.value.decree_basis
 documentId.value=details.value.decree_document_id??'';documentMode.value='existing';reason.value='';expectedVersion.value=props.expertise.version;reset();editing.value=true;await loadOptions()
}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave()){editing.value=false;requests.cancel();reset()}}
function acceptVersion(){expectedVersion.value=props.expertise.version;reset()}
function submit(){if(uncertain.value||details.value.can_edit&&!invalid.value&&!conflict.value&&!loading.value&&!optionsError.value)void command.submit()}
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
 <section data-case-panel class="card stack-card"><div class="section-heading"><div><p class="eyebrow">Орган · дело · материалы</p><h2>Сведения дела</h2><p class="muted compact">{{details.source==='typed'?'Уточнённые сведения карточки':details.source==='history'?'Сведения сохранённого журнала':'Новая работа · сведения ещё не заполнены'}}</p></div><button v-if="details.can_edit&&!editing" data-case-edit @click="start">Редактировать</button></div>
  <dl class="work-facts"><div><dt>Тип органа</dt><dd>{{details.authority_type?.name||details.authority_type_raw||'Неизвестно'}}</dd></div><div v-for="[field,label] in caseFields" :key="field"><dt>{{label}}</dt><dd>{{details[field]||'Не указано'}}</dd></div><div v-if="constructionEligible"><dt>Самовольное строение</dt><dd>{{details.decree3214?'Да':'Не отмечено'}}</dd></div></dl>
  <p v-if="details.decree_basis">{{details.decree_basis}}</p><BasisPreview v-if="details.decree_document" :document="details.decree_document" heading="Основание 3214-р"/>
  <form v-if="editing" data-case-form class="inset-form form-grid" @submit.prevent="submit"><ApiMessage :error="error"/><ApiMessage :error="optionsError"/><p v-if="loading" role="status">Загрузка типов органов…</p><button v-if="optionsError" type="button" @click="loadOptions">Повторить загрузку типов</button>
   <p v-if="uncertain" class="message">Ответ не получен. Повтор отправит ту же попытку; документ не будет создан повторно.</p><p v-if="!details.can_edit" class="message message-error">Право изменения недоступно. Ввод сохранён.</p>
   <p v-if="conflict&&!uncertain" class="message">Карточка изменилась. Обновите серверные сведения; ввод останется. <button v-if="expectedVersion!==expertise.version" data-case-accept-version type="button" @click="acceptVersion">Принять версию {{expertise.version}} для новой попытки</button></p>
   <fieldset data-case-fields class="form-grid" :disabled="busy||uncertain||!details.can_edit||loading">
    <label>Тип назначившего органа<select v-model="authority" name="case_authority_type_id"><option value="">Неизвестно / не уточнён</option><option v-for="item in types" :key="item.id" :value="item.id">{{item.name}}{{item.is_active?'':' (неактивен, использовался)'}}</option></select></label>
    <div class="form-columns"><label v-for="[field,label] in caseFields" :key="field">{{label}}<textarea v-if="['case_description','inventory','questions_text','basis_text'].includes(field)" v-model="text[field]" :name="`case_${field}`" rows="3" maxlength="100000"/><input v-else v-model="text[field]" :name="`case_${field}`" :maxlength="field==='case_number'?500:100000"/></label></div>
    <p class="muted compact">Текст вопросов не заменяет числа Q/R/S/T. Реквизиты не заменяют документ-основание поступления. Пустые сведения остаются неизвестными.</p>
    <label v-if="constructionEligible" class="check-label"><input type="checkbox" name="case_decree3214" :checked="decree==='true'" @change="toggleConstruction"/>Самовольное строение <small>Учитывать в графе3214-р. Дополнительный документ и пояснение необязательны.</small></label>
    <template v-if="constructionEligible&&decree==='true'"><label>Пояснение и реквизиты основания 3214-р (необязательно)<textarea v-model="basis" name="case_decree_basis" rows="2"/></label><DocumentPicker ref="documentForm" v-model="documentId" v-model:mode="documentMode" name="case_document_id" :document="details.decree_document" :department-id="expertise.department.id" :busy="busy||uncertain" heading="Основание 3214-р (необязательно)" saved-note="Сведения дела сохраняются отдельно." @changed="reset"/></template>
    <label>Основание изменения<textarea v-model="reason" name="case_reason" required rows="2"/></label>
   </fieldset>
   <div class="button-row"><button data-case-submit class="button-primary" :disabled="busy||!uncertain&&(invalid||conflict||loading||!!optionsError||!details.can_edit)" :formnovalidate="uncertain">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить сведения'}}</button><button type="button" :disabled="busy||uncertain" @click="cancel">Отмена</button></div>
  </form><FactHistory :revisions="details.revisions" :labels="caseLabels"/>
 </section>
</template>
<style scoped>dd{white-space:pre-wrap;overflow-wrap:anywhere}.form-columns{align-items:start}</style>
