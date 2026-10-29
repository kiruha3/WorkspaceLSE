<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {RouterLink,useRoute,useRouter} from 'vue-router'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import {canManageStorage,validStorageRoot,type StorageRoot,type SavedStorageRoot,type StorageCheckStatus} from '../../api/storage'
import {useSessionStore} from '../../stores/session'
import {useDirtyGuard} from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter()
const reads=new LatestRequest(),probes=new LatestRequest()
const denied=ref(false),enabled=computed(()=>!denied.value&&canManageStorage(session.user))
const initialYear=Number(route.query.year),year=ref(Number.isInteger(initialYear)&&initialYear>=1900&&initialYear<=9999?initialYear:new Date().getFullYear())
const source=ref<StorageRoot|null>(null),path=ref(''),loading=ref(false),busy=ref(false),checking=ref(false)
const dirty=ref(false),uncertain=ref(false),saved=ref(false),error=ref<unknown>(null),writeError=ref<unknown>(null),checkError=ref<unknown>(null)
const checkResult=ref<StorageCheckStatus|null>(null)
type Attempt={key:string;year:number;body:{path:string;expected_version:number}}
const attempt=ref<Attempt|null>(null)
const retryKey=computed(()=>`ais:storage-root:${session.user?.id??''}`)
const locked=computed(()=>busy.value||uncertain.value)
const yearPending=computed(()=>source.value?.year!==Number(year.value))
const confirmLeave=useDirtyGuard(()=>dirty.value||locked.value,router)
let generation=0

function fill(value:StorageRoot){source.value=value;year.value=value.year;path.value=value.path;dirty.value=false}
function forget(){try{sessionStorage.removeItem(retryKey.value)}catch{/* Nothing to replay after a confirmed result. */}}
function authorizationDenied(cause:unknown){
 if(!(cause instanceof ApiError)||![401,403].includes(cause.status))return false
 forget();denied.value=true
 void session.refresh().catch(()=>{/* Session store handles an unavailable refresh. */})
 return true
}
function restore(){
 try{
  const raw=sessionStorage.getItem(retryKey.value)
  if(!raw)return false
  const value=JSON.parse(raw) as Attempt
  if(typeof value?.key!=='string'||!value.key||value.key.length>100||!validStorageRoot({year:value.year,path:value.body?.path,version:value.body?.expected_version,read_only:true}))throw new Error('Invalid attempt')
  attempt.value=value;fill({year:value.year,path:value.body.path,version:value.body.expected_version,read_only:true})
  dirty.value=true;uncertain.value=true;return true
 }catch{forget();return false}
}
async function load(){
 if(!enabled.value||locked.value||checking.value||!confirmLeave())return
 const target=Number(year.value)
 if(!Number.isInteger(target)||target<1900||target>9999){error.value=new ApiError(400,'validation_error','Укажите год от 1900 до 9999.');return}
 loading.value=true;error.value=null;saved.value=false;checkResult.value=null;checkError.value=null
 try{
  await reads.run(signal=>api.request<StorageRoot>(`/document-storage/${target}/`,{signal}),value=>{
   if(!validStorageRoot(value)||value.year!==target)throw new ApiError(200,'invalid_response','Не получена настройка выбранного года.')
   fill(value);attempt.value=null;writeError.value=null;loading.value=false
  })
 }catch(cause){if(!authorizationDenied(cause)){error.value=cause;loading.value=false}}
}
async function submit(){
 if(!enabled.value||locked.value&&!uncertain.value||loading.value||checking.value||yearPending.value||!source.value||busy.value)return
 if(!attempt.value&&!path.value.trim()){writeError.value=new ApiError(400,'validation_error','Укажите полный путь к серверной папке.');return}
 if(!attempt.value)attempt.value={key:newCommandKey(),year:source.value.year,body:{path:path.value.trim(),expected_version:source.value.version}}
 const packet=attempt.value,stamp=generation
 busy.value=true;writeError.value=null;saved.value=false
 try{
  try{sessionStorage.setItem(retryKey.value,JSON.stringify(packet))}catch{throw new ApiError(400,'retry_storage_unavailable','Не удалось сохранить попытку в этой вкладке. Запрос не отправлен.')}
  const value=await api.request<SavedStorageRoot>(`/document-storage/${packet.year}/`,{method:'PUT',body:packet.body,headers:{'Idempotency-Key':packet.key}})
  if(stamp!==generation)return
  if(!validStorageRoot(value)||value.year!==packet.year||value.version<1||!value.event?.id)throw new ApiError(200,'invalid_response','Не получено подтверждение. Повторите ту же попытку.')
  fill(value);forget();attempt.value=null;uncertain.value=false;saved.value=true
 }catch(cause){
  if(stamp===generation&&!authorizationDenied(cause)){writeError.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response';if(!uncertain.value){forget();attempt.value=null}}
 }finally{if(stamp===generation)busy.value=false}
}
async function check(){
 if(!enabled.value||locked.value||loading.value||checking.value||yearPending.value||!path.value.trim())return
 checking.value=true;checkError.value=null;checkResult.value=null
 const selectedPath=path.value.trim()
 try{
  await probes.run(signal=>api.request<{status:StorageCheckStatus;read_only:boolean}>('/document-storage/check/',{method:'POST',body:{path:selectedPath},signal}),value=>{
   if(value?.read_only!==true||!['available','unavailable','timeout'].includes(value.status))throw new ApiError(200,'invalid_response','Не получен результат проверки папки.')
   checkResult.value=value.status;checking.value=false
  })
 }catch(cause){if(!authorizationDenied(cause)){checkError.value=cause;checking.value=false}}
}
watch([path,year],()=>{probes.cancel();checking.value=false;checkResult.value=null;checkError.value=null;saved.value=false},{flush:'sync'})
watch(()=>session.user?.id,()=>{denied.value=false},{flush:'sync'})
watch([enabled,()=>session.user?.id],([allowed])=>{
 generation++;reads.cancel();probes.cancel();loading.value=false;busy.value=false;checking.value=false
 source.value=null;path.value='';dirty.value=false;uncertain.value=false;attempt.value=null;checkResult.value=null;saved.value=false;error.value=null;writeError.value=null
 if(allowed&&!restore())void load()
},{immediate:true})
onBeforeUnmount(()=>{generation++;reads.cancel();probes.cancel()})
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Настройки учреждения</p><h1>Папки документов</h1><p class="muted">Корень документов по годам. К папке обращается сервер Django, а не браузер сотрудника.</p></div><RouterLink to="/settings">← Настройки</RouterLink></div>
 <p v-if="!enabled" class="message">Нужно право «Настраивать папки документов» по учреждению и поддержка модуля сервером.</p>
 <section v-else class="card stack-card storage-settings">
  <div class="storage-mode"><strong>Только чтение</strong><span>Не создаём, не перемещаем и не удаляем файлы.</span></div>
  <div class="year-choice"><label>Год документов<input v-model.number="year" name="storage_year" type="number" min="1900" max="9999" :disabled="locked||loading||checking"/></label><button data-load-storage-year type="button" :disabled="locked||loading||checking" @click="load">{{loading?'Загрузка…':'Открыть настройки года'}}</button></div>
  <ApiMessage :error="error"/>
  <p v-if="loading" class="state">Загрузка настройки…</p>
  <form v-if="source" data-storage-form class="stack-card" @submit.prevent="submit">
   <p v-if="yearPending" class="message">Откройте настройки выбранного года перед изменением пути.</p>
   <ApiMessage :error="writeError"/>
   <label>Корневая папка на сервере<input v-model="path" name="storage_path" type="text" maxlength="2000" required autocomplete="off" spellcheck="false" :disabled="locked||loading||checking||yearPending" placeholder="\\сервер\общая-папка\экспертизы 2026 год" @input="dirty=true"/></label>
   <p class="muted compact">Укажите полный UNC-путь либо путь к каталогу, подключённому на сервере. Браузерный выбор папки на вашем компьютере не подключает её к Django.</p>
   <p v-if="uncertain" class="message">Ответ о сохранении не получен. Поля зафиксированы; повтор использует прежний путь и ключ.</p>
   <p v-if="saved" class="message message-success">Настройка сохранена. Доступ к папке отдельно проверяется кнопкой ниже.</p>
   <div class="button-row"><button class="button-primary" type="submit" :formnovalidate="uncertain" :disabled="busy||loading||checking||yearPending">{{busy?'Сохранение…':uncertain?'Повторить ту же попытку':'Сохранить настройку'}}</button><button data-check-storage type="button" :disabled="locked||loading||checking||yearPending||!path.trim()" @click="check">{{checking?'Проверка доступа…':'Проверить доступ сервером'}}</button></div>
   <ApiMessage :error="checkError"/>
   <p v-if="checkResult" data-storage-check-result class="message" :class="{'message-success':checkResult==='available'}" role="status"><template v-if="checkResult==='available'">Папка доступна серверу для чтения на момент проверки.</template><template v-else-if="checkResult==='timeout'">Сервер не дождался ответа папки за 5 секунд. Проверьте подключение и повторите.</template><template v-else>Источник недоступен: проверьте путь и доступ учётной записи, под которой работает Django.</template></p>
   <p class="muted compact">Проверка читает указанный путь, но не сохраняет его. Версия настройки {{source.year}} года: {{source.version}}.</p>
  </form>
  <div class="storage-next"><h2>Как это связано с экспертизами</h2><p>Например, номер <code>1/1-1-26</code> соответствует папке <code>1_1-1-26</code>. Номера и исторические отделы сохраняются.</p><p class="muted compact">Сопоставление папок с экспертизами и открытие файлов из них — следующий этап. Пока сохранение настройки не создаёт ссылки, не импортирует документы и не меняет рабочие записи.</p></div>
 </section>
</template>
<style scoped>
.storage-settings{max-width:1100px}.storage-settings label{display:flex;flex-direction:column;gap:8px}.storage-mode{display:flex;flex-wrap:wrap;gap:12px;padding:14px 18px;background:var(--surface-soft,#f3f6ef);border-radius:10px}.year-choice{display:flex;align-items:end;gap:12px;flex-wrap:wrap}.year-choice input{max-width:180px}.storage-next{border-top:1px solid var(--border,#dce4d7);padding-top:18px}.storage-next h2{font-size:18px}.storage-next p{line-height:1.65}
</style>
