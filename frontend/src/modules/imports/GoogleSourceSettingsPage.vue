<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {RouterLink,useRoute,useRouter} from 'vue-router'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import {institutionPermission} from '../../api/reportPlans'
import type {GoogleSourceSettings,GoogleSourceSettingsResult} from '../../api/imports'
import {useSessionStore} from '../../stores/session'
import {useDirtyGuard} from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter(),requests=new LatestRequest()
const enabled=computed(()=>institutionPermission(session.user,'imports.source.manage')&&Boolean(session.user?.supported_modules?.includes('journal_source_settings')))
const source=ref<GoogleSourceSettings|null>(null),url=ref(''),gid=ref('0'),sheetName=ref('Лист1')
const loading=ref(false),busy=ref(false),dirty=ref(false),uncertain=ref(false),error=ref<unknown>(null),writeError=ref<unknown>(null),saved=ref(false)
type SourceAttempt={key:string;body:{url:string;gid:string;sheet_name:string;expected_version:number}}
const attempt=ref<SourceAttempt|null>(null)
const storageKey=computed(()=>`ais:journal-source-settings:${session.user?.id??''}`)
const locked=computed(()=>busy.value||uncertain.value)
const back=computed(()=>typeof route.query.return==='string'&&/^\/(?:expertises|imports)(?:\?|$)/.test(route.query.return)?route.query.return:'/expertises')
let generation=0
const confirmLeave=useDirtyGuard(()=>dirty.value||locked.value,router)
watch(url,value=>{
 try{const parsed=new URL(value),valueGid=new URLSearchParams(parsed.hash.slice(1)).get('gid')??parsed.searchParams.get('gid');if(valueGid&&/^[0-9]{1,10}$/.test(valueGid))gid.value=valueGid}catch{/* Incomplete links remain editable. */}
},{flush:'sync'})
function fill(value:GoogleSourceSettings){source.value=value;url.value=value.url;gid.value=value.gid;sheetName.value=value.sheet_name;dirty.value=false}
function valid(value:GoogleSourceSettings){return typeof value?.url==='string'&&typeof value.gid==='string'&&typeof value.sheet_name==='string'&&Number.isInteger(value.version)&&value.version>=0}
function forgetAttempt(){try{window.sessionStorage.removeItem(storageKey.value)}catch{/* The completed command no longer needs a retry. */}}
function restoreAttempt(){
 try{
  const raw=window.sessionStorage.getItem(storageKey.value)
  if(!raw)return false
  const packet=JSON.parse(raw) as SourceAttempt
  if(!packet||typeof packet.key!=='string'||!packet.key||packet.key.length>100||!valid({...packet.body,version:packet.body?.expected_version}))throw new Error('Invalid stored source attempt')
  attempt.value=packet;fill({...packet.body,version:packet.body.expected_version});dirty.value=true;uncertain.value=true;saved.value=false
  return true
 }catch{forgetAttempt();return false}
}
async function load(){
 if(!enabled.value||locked.value||!confirmLeave())return
 loading.value=true;error.value=null;saved.value=false
 try{await requests.run(signal=>api.request<GoogleSourceSettings>('/imports/google-source/settings/',{signal}),value=>{if(!valid(value))throw new ApiError(200,'invalid_response','Не получена настройка источника.');fill(value);attempt.value=null;writeError.value=null;loading.value=false})}
 catch(cause){error.value=cause;loading.value=false}
}
async function submit(){
 if(!enabled.value||busy.value||loading.value||!source.value)return
 if(!attempt.value&&(!url.value.trim()||!/^[0-9]{1,10}$/.test(gid.value.trim())||!sheetName.value.trim())){writeError.value=new ApiError(400,'validation_error','Укажите ссылку, числовой gid и название листа.');return}
 const stamp=generation
 if(!attempt.value)attempt.value={key:newCommandKey(),body:{url:url.value.trim(),gid:gid.value.trim(),sheet_name:sheetName.value.trim(),expected_version:source.value.version}}
 const packet=attempt.value
 busy.value=true;writeError.value=null;saved.value=false
 try{
  try{window.sessionStorage.setItem(storageKey.value,JSON.stringify(packet))}catch{throw new ApiError(400,'retry_storage_unavailable','Не удалось сохранить попытку в этой вкладке. Разрешите хранилище браузера и повторите; запрос не отправлен.')}
  const value=await api.request<GoogleSourceSettingsResult>('/imports/google-source/settings/',{method:'PUT',body:packet.body,headers:{'Idempotency-Key':packet.key}})
  if(stamp!==generation)return
  if(!valid(value)||value.version<1||!value.event?.id)throw new ApiError(200,'invalid_response','Не получено подтверждение сохранения. Повторите ту же попытку.')
  fill(value);forgetAttempt();attempt.value=null;uncertain.value=false;saved.value=true
 }catch(cause){if(stamp===generation){writeError.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response';if(!uncertain.value){forgetAttempt();attempt.value=null}}}
 finally{if(stamp===generation)busy.value=false}
}
watch([enabled,()=>session.user?.id],([allowed,userId],previous)=>{
 generation++;requests.cancel();busy.value=false;loading.value=false
 if(previous&&previous[1]!==userId){source.value=null;attempt.value=null;dirty.value=false;uncertain.value=false;saved.value=false;writeError.value=null}
 if(allowed&&!restoreAttempt()&&!dirty.value&&!attempt.value)void load()
},{immediate:true})
onBeforeUnmount(()=>{generation++;requests.cancel()})
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Источник журнала</p><h1>Настройка Google-таблицы</h1><p class="muted">Общий источник учреждения. Сохранение не запускает импорт и не изменяет Google-таблицу.</p></div><RouterLink data-back-from-source-settings :to="back">← Назад</RouterLink></div>
 <p v-if="!enabled" class="message">Нет права «Настраивать источник Google-таблицы» или сервер не поддерживает настройку.</p>
 <section v-else class="card stack-card source-settings">
  <ApiMessage :error="error"/><p v-if="loading" class="state">Загрузка настройки…</p>
  <p v-if="saved" class="message message-success">Источник сохранён. Новые обновления журнала используют эту таблицу без перезапуска сервера.</p>
  <form v-if="source" data-source-settings-form class="stack-card" @input="dirty=true;saved=false" @submit.prevent="submit">
   <ApiMessage :error="writeError"/>
   <label>Ссылка Google Sheets<input v-model="url" name="source_url" type="url" required maxlength="2000" :disabled="locked||loading" placeholder="https://docs.google.com/spreadsheets/d/…/edit#gid=0"/></label>
   <div class="form-grid"><label>ID листа (gid)<input v-model="gid" name="source_gid" inputmode="numeric" pattern="[0-9]{1,10}" required maxlength="10" :disabled="locked||loading"/></label><label>Название листа<input v-model="sheetName" name="source_sheet_name" required maxlength="255" :disabled="locked||loading"/></label></div>
   <p class="muted compact">При вставке ссылки gid подставляется автоматически. Можно изменить его вручную: используется именно значение в поле gid. Название служит подписью листа, а не выбирает его.</p>
   <p v-if="uncertain" class="message">Ответ не получен. Поля зафиксированы; повтор отправит прежние значения и ключ, без повторного изменения настройки.</p>
   <div class="button-row"><button type="submit" class="button-primary" :formnovalidate="uncertain" :disabled="busy||loading">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить источник'}}</button><button type="button" :disabled="locked||loading" @click="load">Обновить настройку</button></div>
   <p class="muted compact">Версия настройки: {{source.version}}. Старые снимки импорта остаются без изменений. Для чтения данных вернитесь в реестр и нажмите «Обновить из таблицы».</p>
  </form>
  <button v-else-if="error" :disabled="loading" @click="load">Повторить загрузку</button>
 </section>
</template>
<style scoped>.source-settings{max-width:1000px}.source-settings label{display:flex;flex-direction:column;gap:8px}.source-settings .form-grid{grid-template-columns:minmax(120px,1fr) minmax(180px,2fr)}@media(max-width:640px){.source-settings .form-grid{grid-template-columns:1fr}}</style>
