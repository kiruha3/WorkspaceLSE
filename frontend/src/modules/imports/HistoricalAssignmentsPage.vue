<script setup lang="ts">
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {RouterLink,useRouter} from 'vue-router'
import {ApiError,LatestRequest,useApi} from '../../api/client'
import {newCommandKey} from '../../api/commandKey'
import {institutionPermission} from '../../api/reportPlans'
import {useSessionStore} from '../../stores/session'
import {useDirtyGuard} from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import HelpTip from '../../shared/ui/HelpTip.vue'
import SortableTable from '../../shared/ui/SortableTable.vue'

interface Row {expertise_id:string;number:string;state:string;expected_version:number;proposal_hash:string;batch_id:string;source_row:number;executor_raw:string;specialty:string|null;operational:boolean;employees:{id:string;full_name:string}[];eligible:boolean;blockers:string[]}
interface Preview {results:Row[];eligible_count:number}
interface Choice {expertise_id:string;expected_version:number;proposal_hash:string}
interface Result {applied_count:number;expertise_ids:string[];event_ids:string[]}
const api=useApi(),session=useSessionStore(),router=useRouter(),requests=new LatestRequest()
const enabled=computed(()=>session.user?.supported_modules?.includes('historical_assignment_import')&&institutionPermission(session.user,'imports.results.view')&&session.can('expertise.view'))
const canApply=computed(()=>enabled.value&&institutionPermission(session.user,'imports.apply')&&session.can('expertise.assign'))
const accessStamp=computed(()=>JSON.stringify(['imports.results.view','imports.apply','expertise.view','expertise.assign'].map(code=>session.user?.access[code]??[])))
const data=ref<Preview|null>(null),error=ref<unknown>(null),writeError=ref<unknown>(null),loading=ref(false),busy=ref(false),uncertain=ref(false)
const selected=ref<string[]>([]),search=ref(''),onlyAvailable=ref(false),reason=ref('Перенос подтверждённых исторических соответствий после импорта')
const result=ref<Result|null>(null),attempt=ref<{key:string;body:{selections:Choice[];reason:string}}|null>(null)
const locked=computed(()=>busy.value||uncertain.value||Boolean(result.value))
const names=(row:Row)=>row.employees.map(employee=>employee.full_name).join(', ')
const states:Record<string,string>={in_progress:'В работе',suspended:'Приостановлена',completed:'Завершена',without_execution:'Без исполнения'}
const shown=computed(()=>{const term=search.value.toLocaleLowerCase().trim();return(data.value?.results??[]).filter(row=>(!onlyAvailable.value||row.eligible)&&(!term||`${row.number} ${row.executor_raw} ${names(row)}`.toLocaleLowerCase().includes(term)))})
let generation=0
const confirmLeave=useDirtyGuard(()=>Boolean(selected.value.length||uncertain.value),router,()=>busy.value)
async function load(){
 const stamp=++generation;requests.cancel();loading.value=true;error.value=null;data.value=null
 if(!enabled.value){loading.value=false;return}
 try{await requests.run(signal=>api.request<Preview>('/imports/historical-assignments/',{signal}),value=>{if(stamp===generation){data.value=value;loading.value=false}})}
 catch(cause){if(stamp===generation){error.value=cause;loading.value=false}}
}
function select(row:Row,on:boolean){
 if(locked.value||!canApply.value||!row.eligible)return
 selected.value=on?[...new Set([...selected.value,row.expertise_id])]:selected.value.filter(id=>id!==row.expertise_id)
 attempt.value=null;writeError.value=null
}
function selectVisible(){if(!locked.value&&canApply.value){selected.value=[...new Set([...selected.value,...shown.value.filter(row=>row.eligible).map(row=>row.expertise_id)])];attempt.value=null}}
function clear(){if(!locked.value){selected.value=[];attempt.value=null}}
async function refresh(){if(locked.value&&!result.value||!confirmLeave())return;selected.value=[];attempt.value=null;result.value=null;writeError.value=null;await load()}
async function apply(){
 if(!canApply.value||busy.value||result.value||!selected.value.length)return
 const stamp=generation
 if(!attempt.value){
  const selections=(data.value?.results??[]).filter(row=>selected.value.includes(row.expertise_id)&&row.eligible).map(({expertise_id,expected_version,proposal_hash})=>({expertise_id,expected_version,proposal_hash})).sort((a,b)=>a.expertise_id.localeCompare(b.expertise_id))
  if(!selections.length||selections.length>1000)return
  if(!window.confirm(`Создать текущие назначения в ${selections.length} экспертизах по подтверждённым историческим соответствиям?\nДата назначения — сегодня. Номера, отделы и исторические сведения сохранятся.\nПодтверждение оснований для работы остаётся отдельным действием в карточке.`)||stamp!==generation||!canApply.value)return
  attempt.value={key:newCommandKey(),body:{selections,reason:reason.value.trim()}}
 }
 const packet=attempt.value
 busy.value=true;writeError.value=null
 try{
  const response=await api.request<Result>('/imports/historical-assignments/',{method:'POST',body:packet.body,headers:{'Idempotency-Key':packet.key}})
  if(stamp!==generation)return
  const expected=packet.body.selections.map(row=>row.expertise_id).sort()
  if(response.applied_count!==expected.length||!Array.isArray(response.expertise_ids)||JSON.stringify([...response.expertise_ids].sort())!==JSON.stringify(expected)||!Array.isArray(response.event_ids)||response.event_ids.length!==expected.length)throw new ApiError(200,'invalid_response','Не получен полный протокол переноса. Повторите ту же попытку.')
  result.value=response;selected.value=[];attempt.value=null;uncertain.value=false
 }catch(cause){if(stamp===generation){writeError.value=cause;uncertain.value=!(cause instanceof ApiError)||cause.status>=500||cause.code==='invalid_response';if(!uncertain.value)attempt.value=null}}
 finally{if(stamp===generation)busy.value=false}
}
watch([enabled,()=>session.user?.id,accessStamp],()=>{selected.value=[];attempt.value=null;result.value=null;uncertain.value=false;busy.value=false;void load()},{immediate:true})
onBeforeUnmount(()=>{generation++;requests.cancel()})
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Настройки · Импорт</p><h1>Исполнители из журнала <HelpTip label="Исторические соответствия">Разовый перенос явно сопоставленных сотрудников в текущие назначения. При обычном обновлении журнала перенос автоматически не запускается. Дата назначения — момент применения, прежние исторические даты сохраняются.</HelpTip></h1></div><RouterLink to="/settings">← Настройки</RouterLink></div>
 <p v-if="!enabled" class="message">Нужны права на просмотр результатов импорта и экспертиз, а также поддержка переноса на сервере.</p>
 <template v-else>
  <ApiMessage :error="error"/><p v-if="loading" class="state">Проверяем исторические соответствия…</p>
  <p v-if="!canApply" class="message">Для применения нужны права «Применять подтверждённый пакет переноса» и «Назначать экспертов» в отделе работы.</p>
  <section v-if="data" class="card transfer-card">
   <p v-if="result" class="message message-success" role="status">Перенесено экспертиз: {{result.applied_count}}. Назначения сохранены; номера и история не менялись.</p>
   <div class="transfer-toolbar"><label class="transfer-search">Номер или сотрудник<input v-model="search" type="search" placeholder="Поиск по списку"/></label><label class="transfer-check"><input v-model="onlyAvailable" type="checkbox"/>Только доступные</label><span class="muted">Доступно: {{data.eligible_count}} из {{data.results.length}}</span><button :disabled="loading||busy||uncertain" @click="refresh">Обновить</button></div>
   <div class="button-row"><button data-select-eligible :disabled="locked||!canApply||!shown.some(row=>row.eligible)" @click="selectVisible">Выбрать доступные в списке</button><button :disabled="locked||!selected.length" @click="clear">Снять выбор</button><span class="muted">Выбрано: {{selected.length}}</span></div>
   <p v-if="!data.results.length" class="state">Исторических экспертиз нет.</p><p v-else-if="!shown.length" class="state">По этим условиям ничего не найдено.</p>
   <div v-else class="table-scroll"><SortableTable :rows="shown" :columns="[{key:'choice',label:'Выбор',sortable:false},{key:'number',label:'Экспертиза',value:r=>r.number},{key:'source',label:'В журнале',value:r=>r.executor_raw},{key:'employees',label:'Назначить',value:names},{key:'status',label:'Проверка',value:r=>r.blockers.join(' ')}]" v-slot="{rows}">
    <tr v-for="row in rows" :key="row.expertise_id"><td><input :data-work="row.expertise_id" type="checkbox" :aria-label="`Перенести исполнителей ${row.number}`" :checked="selected.includes(row.expertise_id)" :disabled="locked||!canApply||!row.eligible" @change="select(row,($event.target as HTMLInputElement).checked)"/></td><td><RouterLink :to="`/expertises/${row.expertise_id}`">{{row.number}}</RouterLink><small>{{states[row.state]??row.state}} · {{row.specialty??'Без специальности'}}</small></td><td>{{row.executor_raw||'—'}}<small><RouterLink :to="`/imports/${row.batch_id}/reconciliation?search=${encodeURIComponent(row.number)}`">Сверка · строка {{row.source_row}}</RouterLink></small></td><td>{{names(row)||'Не сопоставлен'}}</td><td><template v-if="row.eligible"><span class="badge">Можно перенести</span><small v-if="!row.operational">Основание для дальнейшей работы подтвердите в карточке.</small></template><span v-for="blocker in row.blockers" :key="blocker" class="blocker">{{blocker}}</span></td></tr>
   </SortableTable></div>
   <template v-if="!result"><div class="transfer-apply"><label>Основание переноса (необязательно)<input v-model="reason" :disabled="locked" maxlength="2000"/></label><ApiMessage :error="writeError"/><p v-if="uncertain" class="message">Ответ не получен. Выбор зафиксирован: повтор отправит тот же пакет и ключ, без дублей.</p><p v-if="selected.length>1000" class="message">За один раз можно перенести до 1000 экспертиз. Уменьшите выбор.</p><button data-apply-assignments class="button-primary" :disabled="busy||!canApply||!selected.length||selected.length>1000" @click="apply">{{busy?'Сохраняем…':uncertain?'Повторить ту же попытку':`Применить выбранное (${selected.length})`}}</button></div></template>
  </section>
  <button v-if="error" :disabled="loading" @click="load">Повторить загрузку</button>
 </template>
</template>
<style scoped>
.transfer-card{display:grid;gap:14px;padding:18px}.transfer-toolbar{display:flex;align-items:end;flex-wrap:wrap;gap:14px}.transfer-search{min-width:230px;flex:1}.transfer-search input,.transfer-apply input{display:block;width:100%;margin-top:5px}.transfer-check{display:flex;align-items:center;gap:7px;align-self:center}.transfer-apply{display:grid;gap:12px;border-top:1px solid var(--border);padding-top:14px}.transfer-apply>label{max-width:680px}.transfer-apply>button{justify-self:start}.transfer-card td{vertical-align:top;padding:10px 12px;max-width:360px;overflow-wrap:anywhere}.transfer-card small{display:block;color:var(--muted);font-size:12px;margin-top:4px}.blocker{display:block;font-size:12px;margin-bottom:3px}input[type=checkbox]{width:18px;height:18px}.transfer-card .button-row{align-items:center}
</style>
