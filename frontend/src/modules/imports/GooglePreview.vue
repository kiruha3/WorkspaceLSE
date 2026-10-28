<script setup lang="ts">
import { computed,inject,onBeforeUnmount,ref,watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError,LatestRequest,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { ConfiguredGoogleSource,GooglePreviewPayload,GoogleSourceInfo,ImportBatch,ImportPreviewResponse } from '../../api/imports'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const props=defineProps<{canCreate:boolean}>(),emit=defineEmits<{created:[ImportBatch]}>(),api=useApi(),session=useSessionStore(),requests=new LatestRequest()
const enabled=computed(()=>session.googlePreviewEnabled&&session.importPreviewEnabled&&session.can('imports.results.view'))
const canStart=computed(()=>props.canCreate&&session.can('imports.preview')),source=ref<GoogleSourceInfo|null>(null),loading=ref(false),error=ref<unknown>(null)
const editing=ref(false),selected=ref<ConfiguredGoogleSource|null>(null),reason=ref(''),busy=ref(false),writeError=ref<unknown>(null),uncertain=ref(false),saved=ref(false)
const attempt=ref<{body:GooglePreviewPayload;key:string}|null>(null),normalizedReason=computed(()=>reason.value.trim())
const confirmLeave=useDirtyGuard(()=>editing.value&&!saved.value&&Boolean(normalizedReason.value||attempt.value||busy.value),inject(routerKey,undefined))
watch(normalizedReason,()=>{attempt.value=null;uncertain.value=false;writeError.value=null},{flush:'sync'})
async function load(){
  if(!enabled.value||editing.value)return;loading.value=true;error.value=null;source.value=null
  try{await requests.run(signal=>api.request<GoogleSourceInfo>('/imports/google-source/',{signal}),value=>{source.value=value;loading.value=false})}catch(cause){error.value=cause;loading.value=false}
}
function start(){if(!canStart.value||!source.value?.configured)return;selected.value={...source.value};reason.value='';attempt.value=null;writeError.value=null;uncertain.value=false;saved.value=false;editing.value=true}
function cancel(){if(!busy.value&&confirmLeave()){editing.value=false;selected.value=null;attempt.value=null;saved.value=true}}
async function submit(){
  if(busy.value||!enabled.value||(!canStart.value&&!uncertain.value)||!selected.value||(!attempt.value&&!normalizedReason.value))return
  busy.value=true;writeError.value=null
  try{
    if(!attempt.value)attempt.value={body:{reason:normalizedReason.value,spreadsheet_id:selected.value.spreadsheet_id,gid:selected.value.gid},key:newCommandKey()}
    const result=await api.request<ImportPreviewResponse>('/imports/google-preview/',{method:'POST',body:attempt.value.body,headers:{'Idempotency-Key':attempt.value.key}})
    saved.value=true;editing.value=false;emit('created',result.batch)
  }catch(cause){writeError.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response'}finally{busy.value=false}
}
watch(enabled,()=>{requests.cancel();source.value=null;if(enabled.value)void load()},{immediate:true})
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
  <section v-if="enabled" data-google-source class="card stack-card">
    <div class="section-heading"><div><p class="eyebrow">Актуальный источник</p><h2>Google-таблица</h2><p class="muted compact">Только чтение. Исходную таблицу и её доступ не меняем.</p></div><button v-if="!editing" data-google-reload :disabled="loading" @click="load">Обновить сведения об источнике</button></div>
    <ApiMessage :error="error"/><p v-if="loading" class="state">Проверка настройки источника…</p><p v-else-if="source&&!source.configured" class="muted">Google-источник не настроен. Загрузка файла остаётся доступной.</p>
    <template v-if="source?.configured"><p><strong>{{source.label||source.sheet_name}}</strong> · лист {{source.sheet_name}} · gid {{source.gid}}</p><p class="source-address muted compact">{{source.url}}</p><p class="muted compact">Сохраняется снимок значений выбранного листа в CSV. Формулы и другие листы не переносятся; рабочие экспертизы этим действием не создаются.</p><button v-if="canStart&&!editing" data-read-google class="button-primary" @click="start">Проверить актуальную Google-таблицу</button></template>
    <form v-if="editing&&selected" data-google-preview-form class="form-grid" @submit.prevent="submit"><h3>Проверка листа {{selected.sheet_name}}</h3><ApiMessage :error="writeError"/><p v-if="uncertain" class="message">Ответ не получен. Повтор использует прежний источник, основание и ключ, а сервер вернёт сохранённый снимок, если он уже создан.</p><p v-if="!canStart" class="message">Новая проверка больше не разрешена. Подготовленные сведения сохранены.</p><label>Основание проверки Google<textarea v-model="reason" name="google_reason" required rows="2" :disabled="busy||(!canStart&&!uncertain)"/></label><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="uncertain" :disabled="busy||(!canStart&&!uncertain)||(!attempt&&!normalizedReason)">{{busy?'Чтение и сохранение…':uncertain?'Повторить ту же попытку':'Сохранить результат проверки'}}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div><p class="muted compact">Если настройка источника изменилась, завершите эту попытку и явно обновите сведения. Автоматической подмены выбранного листа нет.</p></form>
  </section>
</template>
<style scoped>.source-address{overflow-wrap:anywhere}</style>
