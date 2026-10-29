<script setup lang="ts">
import { computed,onBeforeUnmount,ref,shallowRef } from 'vue'
import { RouterLink,useRoute,useRouter } from 'vue-router'
import { ApiError,useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import { institutionPermission } from '../../api/reportPlans'
import type { GoogleSourceInfo,ImportPreviewResponse } from '../../api/imports'
import { useSessionStore } from '../../stores/session'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter()
const enabled=computed(()=>session.importPreviewEnabled&&session.journalApplicationEnabled&&session.can('imports.results.view')&&session.can('imports.preview'))
const canConfigure=computed(()=>institutionPermission(session.user,'imports.source.manage')&&Boolean(session.user?.supported_modules?.includes('journal_source_settings')))
const busy=ref(false),uncertain=ref(false),error=ref<unknown>(null),upload=ref(false),file=ref<File|null>(null),saved=ref(false)
const attempt=shallowRef<{path:string;body:unknown;key:string;returnTo:string}|null>(null)
let active=true
useDirtyGuard(()=>!saved.value&&Boolean(busy.value||uncertain.value||file.value),router)
function choose(event:Event){if(busy.value||uncertain.value)return;file.value=(event.target as HTMLInputElement).files?.[0]??null;attempt.value=null;error.value=null}
async function send(){
 const packet=attempt.value
 if(!packet)return
 const response=await api.request<ImportPreviewResponse>(packet.path,{method:'POST',body:packet.body,headers:{'Idempotency-Key':packet.key}})
 if(!active)return
 if(!response.batch?.id)throw new ApiError(200,'invalid_response','Сервер не вернул сохранённый источник. Повторите ту же попытку.')
 saved.value=true;uncertain.value=false;file.value=null
 await router.push({path:`/imports/${response.batch.id}/review`,query:{return:packet.returnTo}})
}
async function start(kind:'google'|'file'|'retry'){
 if(busy.value||!enabled.value||uncertain.value&&kind!=='retry')return
 if(kind==='file'&&!file.value)return
 busy.value=true;error.value=null;saved.value=false
 if(kind!=='retry')attempt.value=null
 try{
  if(kind==='google'){
   const source=await api.request<GoogleSourceInfo>('/imports/google-source/')
   if(!active)return
   if(!source.configured)throw new ApiError(400,'not_configured','Google-источник не настроен. Можно загрузить Excel/CSV.')
   attempt.value={path:'/imports/google-preview/',body:{spreadsheet_id:source.spreadsheet_id,gid:source.gid,reason:'Обновление реестра: пользователь запросил свежий перечень изменений Google-таблицы.'},key:newCommandKey(),returnTo:route.fullPath}
  }else if(kind==='file'){
   const body=new FormData();body.append('file',file.value!);body.append('reason','Обновление реестра: пользователь загрузил файл для проверки и выбора изменений.')
   attempt.value={path:'/imports/preview/',body,key:newCommandKey(),returnTo:route.fullPath}
  }
  await send()
 }catch(cause){if(active){error.value=cause;uncertain.value=Boolean(attempt.value)&&(!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response')}}
 finally{if(active)busy.value=false}
}
onBeforeUnmount(()=>{active=false})
</script>
<template>
 <section v-if="enabled||canConfigure" class="card stack-card journal-sync-actions" data-journal-sync>
  <div class="section-heading"><div><h2>Обновление из журнала</h2><p class="muted compact">Сначала перечень «было → станет». В БД попадёт только то, что вы выберете и подтвердите.</p></div><div class="button-row">
   <button v-if="enabled&&session.googlePreviewEnabled" data-read-journal-source class="button-primary" :disabled="busy||uncertain" @click="start('google')">{{busy&&!upload?'Чтение таблицы…':'Обновить из таблицы'}}</button>
   <button v-if="enabled" data-upload-journal-file :disabled="busy||uncertain" @click="upload=!upload">Загрузить Excel/CSV</button>
   <RouterLink v-if="session.can('imports.results.view')" to="/imports">Источники и история</RouterLink>
   <RouterLink v-if="canConfigure" data-configure-journal-source :to="{path:'/imports/source-settings',query:{return:route.fullPath}}">Настроить источник</RouterLink>
  </div></div>
  <ApiMessage :error="error"/>
  <p v-if="uncertain" class="message">Ответ о сохранении источника не получен. Повтор не создаст второй снимок для этой попытки.</p>
  <button v-if="uncertain" :disabled="busy" @click="start('retry')">Повторить ту же попытку</button>
  <form v-if="upload" class="button-row" data-journal-file-form @submit.prevent="start('file')"><label>Первый лист журнала<input name="journal_sync_file" type="file" accept=".xlsx,.csv" :disabled="busy||uncertain" @change="choose"/></label><button type="submit" :disabled="busy||uncertain||!file">{{busy?'Чтение файла…':'Проверить файл'}}</button></form>
  <p class="muted compact">Фильтры реестра не ограничивают импорт. Данные Google и исходный файл не изменяются.</p>
 </section>
</template>
<style scoped>.journal-sync-actions{margin-bottom:20px}.journal-sync-actions h2{margin:0 0 8px}.journal-sync-actions .section-heading{align-items:center;flex-wrap:wrap;gap:16px}</style>
