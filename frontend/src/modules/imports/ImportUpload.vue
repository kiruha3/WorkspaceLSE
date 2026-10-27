<script setup lang="ts">
import { computed,inject,ref,watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { ImportBatch,ImportPreviewResponse } from '../../api/imports'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const props=defineProps<{canCreate:boolean}>(),emit=defineEmits<{created:[ImportBatch];cancel:[]}>(),api=useApi()
const file=ref<File|null>(null),reason=ref(''),busy=ref(false),error=ref<unknown>(null),uncertain=ref(false),saved=ref(false)
const attempt=ref<{file:File;reason:string;key:string}|null>(null),normalizedReason=computed(()=>reason.value.trim())
watch([file,normalizedReason],()=>{attempt.value=null;uncertain.value=false;error.value=null},{flush:'sync'})
const confirmLeave=useDirtyGuard(()=>!saved.value&&Boolean(file.value||normalizedReason.value||attempt.value||busy.value),inject(routerKey,undefined))
function choose(event:Event){file.value=(event.target as HTMLInputElement).files?.[0]??null}
function cancel(){if(!busy.value&&confirmLeave()){saved.value=true;emit('cancel')}}
async function submit(){
  if(busy.value||(!props.canCreate&&!uncertain.value))return
  if(!attempt.value&&(!file.value||!normalizedReason.value))return
  busy.value=true;error.value=null
  try{
    if(!attempt.value)attempt.value={file:file.value!,reason:normalizedReason.value,key:newCommandKey()}
    const body=new FormData();body.append('file',attempt.value.file);body.append('reason',attempt.value.reason)
    const result=await api.request<ImportPreviewResponse>('/imports/preview/',{method:'POST',body,headers:{'Idempotency-Key':attempt.value.key}})
    saved.value=true;emit('created',result.batch)
  }catch(cause){error.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}
  finally{busy.value=false}
}
</script>
<template>
  <form data-import-upload class="form-grid" @submit.prevent="submit"><h2>Новый снимок журнала</h2><ApiMessage :error="error"/><p v-if="uncertain" class="message">Ответ не получен. Повтор использует тот же файл, основание и ключ.</p><p v-if="!canCreate" class="message">Загрузка больше не разрешена. Выбранные сведения сохранены в форме.</p>
    <fieldset class="form-grid" :disabled="busy||(!canCreate&&!uncertain)"><label>Первый лист XLSX или CSV<input name="import_file" type="file" accept=".xlsx,.csv" :required="!file" @change="choose"/></label><p v-if="file" class="muted">{{file.name}} · {{Math.ceil(file.size/1024)}} КБ</p><label>Основание проверки<textarea v-model="reason" name="import_reason" required rows="2"/></label></fieldset>
    <p class="muted compact">Сохранится неизменяемый снимок первого листа. Рабочие экспертизы, сотрудники и события выдачи не создаются.</p><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="uncertain" :disabled="busy||(!canCreate&&!uncertain)||(!attempt&&(!file||!normalizedReason))">{{busy?'Чтение и сохранение…':uncertain?'Повторить ту же попытку':'Проверить источник'}}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
  </form>
</template>
