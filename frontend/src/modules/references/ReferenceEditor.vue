<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { useRouter } from 'vue-router'
import { LatestRequest,useApi } from '../../api/client'
import type { Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useCommandAttempt } from '../../shared/ui/useCommandAttempt'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { closureRules,reportGroups,delayReportGroups } from './catalogs'
const props=defineProps<{catalog:string;item:Reference|null}>(),emit=defineEmits<{saved:[Reference];cancel:[];refresh:[]}>()
const session=useSessionStore(),api=useApi(),router=useRouter(),requests=new LatestRequest()
const code=ref(''),name=ref(props.item?.name??''),isActive=ref(props.item?.is_active??true),group=ref(props.item?.report_group??''),direction=ref('incoming'),department=ref(''),rule=ref('other'),version=ref(props.item?.version??0)
const departments=ref<Reference[]>([]),optionsError=ref<unknown>(null),loading=ref(false)
const hasGroup=computed(()=>['authority-types','delay-reasons'].includes(props.catalog))
const groupOptions=computed(()=>props.catalog==='delay-reasons'?delayReportGroups:reportGroups)
const payload=computed(()=>props.item?{expected_version:version.value,name:name.value.trim(),is_active:isActive.value,...(hasGroup.value?{report_group:group.value||null}:{})}:{code:code.value.trim(),name:name.value.trim(),...(hasGroup.value?{report_group:group.value||null}:props.catalog==='letter-journals'?{direction:direction.value,department_id:department.value||null}:props.catalog==='control-closure-reasons'?{rule:rule.value}:{})})
const stamp=computed(()=>JSON.stringify(payload.value)),initial=stamp.value
const command=useCommandAttempt<Reference>(()=>({path:`/references/${props.catalog}/${props.item?`${props.item.id}/`:''}`,method:props.item?'PATCH':'POST',body:payload.value}),item=>emit('saved',item))
const {busy,uncertain,error,conflict}=command
const confirmLeave=useDirtyGuard(()=>stamp.value!==initial||busy.value||uncertain.value,router)
watch(stamp,command.reset,{flush:'sync'})
const invalid=computed(()=>!name.value.trim()||!props.item&&!code.value.trim())
async function loadDepartments(){loading.value=true;optionsError.value=null;try{await requests.run(signal=>api.allPages<Reference>('/references/departments/?is_active=true',signal),items=>{departments.value=items;loading.value=false})}catch(cause){optionsError.value=cause;loading.value=false}}
if(props.catalog==='letter-journals'&&!props.item)void loadDepartments()
function submit(){if(uncertain.value||session.can('references.manage')&&!invalid.value&&!conflict.value&&!optionsError.value&&!loading.value)void command.submit()}
function cancel(){if(!busy.value&&!uncertain.value&&confirmLeave())emit('cancel')}
function accept(){version.value=props.item!.version;command.reset()}
defineExpose({confirmLeave:()=>!busy.value&&!uncertain.value&&confirmLeave()})
onBeforeUnmount(()=>requests.cancel())
</script>
<template><form data-reference-form class="card form-grid" @submit.prevent="submit"><h2>{{item?'Изменить запись':'Новая запись справочника'}}</h2><p v-if="item" class="muted compact">Код {{item.code}} · версия {{version}}. Код и специальные правила существующей записи не меняются.</p><ApiMessage :error="error"/><ApiMessage :error="optionsError"/><p v-if="uncertain" class="message">Ответ не получен. Данные и ключ попытки сохранены.</p><p v-if="conflict&&!uncertain" class="message">Запись изменилась. Ввод сохранён. <button type="button" @click="emit('refresh')">Обновить серверную запись</button> <button v-if="item&&item.version!==version" data-reference-accept-version type="button" @click="accept">Принять версию {{item.version}}</button></p><button v-if="optionsError" type="button" @click="loadDepartments">Повторить загрузку отделов</button>
 <fieldset data-reference-fields class="form-grid" :disabled="busy||uncertain||loading||!session.can('references.manage')"><label v-if="!item">Стабильный код<input v-model="code" name="reference_code" required maxlength="80"/></label><label>Название<input v-model="name" name="reference_name" required maxlength="300"/></label><label v-if="item" class="check-label"><input v-model="isActive" name="reference_active" type="checkbox"/>Активная запись</label>
 <label v-if="hasGroup">{{catalog==='delay-reasons'?'Группа причин для отчёта':'Группа органов для отчёта'}}<select v-model="group" name="reference_report_group"><option value="">Не определена</option><option v-for="[value,label] in groupOptions" :key="value" :value="value">{{label}}</option></select><small>Неопределённая группа не считается «иной». Изменение группы влияет на новый расчёт отчёта.</small></label>
 <template v-if="!item&&catalog==='letter-journals'"><label>Направление<select v-model="direction" name="reference_direction"><option value="incoming">Входящие</option><option value="outgoing">Исходящие</option></select></label><label>Отдел журнала<select v-model="department" name="reference_department"><option value="">Общий журнал учреждения</option><option v-for="entry in departments" :key="entry.id" :value="entry.id">{{entry.code}} · {{entry.name}}</option></select></label></template>
 <label v-if="!item&&catalog==='control-closure-reasons'">Правило снятия с контроля<select v-model="rule" name="reference_rule"><option v-for="[value,label] in closureRules" :key="value" :value="value">{{label}}</option></select></label>
 </fieldset><div class="button-row"><button data-reference-submit class="button-primary" :disabled="busy||!uncertain&&(invalid||conflict||loading||!!optionsError||!session.can('references.manage'))" :formnovalidate="uncertain">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить'}}</button><button data-reference-cancel type="button" :disabled="busy||uncertain" @click="cancel">Отмена</button></div></form></template>
