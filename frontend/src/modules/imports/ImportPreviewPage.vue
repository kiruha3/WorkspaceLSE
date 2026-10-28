<script setup lang="ts">
import { computed,onBeforeUnmount,reactive,ref,watch } from 'vue'
import { RouterLink,useRoute,useRouter } from 'vue-router'
import { LatestRequest,useApi } from '../../api/client'
import { importTime,importedStates,type ImportBatch,type ImportRow } from '../../api/imports'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import ImportRowDetails from './ImportRowDetails.vue'
const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter(),batchRequests=new LatestRequest(),rowRequests=new LatestRequest()
const enabled=computed(()=>session.importPreviewEnabled&&session.can('imports.results.view')),value=ref<ImportBatch|null>(null),rows=ref<Page<ImportRow>>({count:0,next:null,previous:null,results:[]}),selected=ref<ImportRow|null>(null),loading=ref(false),rowsLoading=ref(false),error=ref<unknown>(null),rowError=ref<unknown>(null)
const keys=['search','severity','state'] as const,filters=reactive({search:'',severity:'',state:''}),currentPage=computed(()=>Math.max(1,Number(route.query.page)||1))
const returnTo=computed(()=>typeof route.query.return==='string'&&/^\/imports(?:\?|$)/.test(route.query.return)?route.query.return:'/imports')
const sourceUrl=computed(()=>value.value&&/^\/api\/v1\/imports\/[a-zA-Z0-9-]+\/source\/$/.test(value.value.source_url)?value.value.source_url:null)
function queryValue(key:string){return typeof route.query[key]==='string'?route.query[key]:route.query[key]?'__invalid_filter__':''}
async function loadBatch(){
  if(!enabled.value)return;loading.value=true;error.value=null
  try{await batchRequests.run(signal=>api.request<ImportBatch>(`/imports/${route.params.id}/`,{signal}),result=>{value.value=result;loading.value=false})}catch(cause){error.value=cause;loading.value=false}
}
async function loadRows(){
  if(!enabled.value)return;rowsLoading.value=true;rowError.value=null;selected.value=null;rows.value={count:0,next:null,previous:null,results:[]}
  const query=new URLSearchParams({...Object.fromEntries(keys.filter(key=>queryValue(key)).map(key=>[key,queryValue(key)])),page:String(currentPage.value)})
  try{await rowRequests.run(signal=>api.request<Page<ImportRow>>(`/imports/${route.params.id}/rows/?${query}`,{signal}),result=>{rows.value=result;rowsLoading.value=false})}catch(cause){rowError.value=cause;rowsLoading.value=false}
}
function filter(page=1){void router.replace({path:route.path,query:{...Object.fromEntries(keys.filter(key=>filters[key]).map(key=>[key,filters[key]])),page:String(page),...(route.query.return?{return:route.query.return}:{})}})}
watch([()=>route.params.id,enabled],()=>{batchRequests.cancel();rowRequests.cancel();value.value=null;rows.value={count:0,next:null,previous:null,results:[]};selected.value=null;if(enabled.value)void loadBatch()},{immediate:true})
watch([()=>route.fullPath,enabled],()=>{rowRequests.cancel();selected.value=null;keys.forEach(key=>{filters[key]=queryValue(key)});if(enabled.value)void loadRows()},{immediate:true})
onBeforeUnmount(()=>{batchRequests.cancel();rowRequests.cancel()})
</script>
<template><p v-if="!enabled" class="state">Предпросмотр переноса недоступен в этой сессии.</p><template v-else><div class="page-heading"><div><p class="eyebrow">Неизменяемый снимок источника</p><h1>{{value?.source_name||'Проверка журнала'}}</h1><p class="muted">Исходные строки и диагностика без изменения рабочих данных.</p></div><RouterLink data-back-to-imports :to="returnTo">← К источникам</RouterLink></div><p class="message">Предпросмотр: рабочие записи ещё не созданы. Затем потребуются сопоставление и отдельное подтверждённое применение.</p><ApiMessage :error="error"/><button v-if="error" :disabled="loading" @click="loadBatch">Повторить загрузку источника</button><p v-if="loading" class="state">Загрузка сведений источника…</p>
  <section v-if="value" class="card stack-card"><div class="section-heading"><h2>{{value.sheet_name}}</h2><a v-if="sourceUrl" :href="sourceUrl" download>Скачать исходный файл</a></div><dl data-import-summary class="work-facts"><div><dt>Всего регистраций в снимке</dt><dd>{{value.summary.row_count}}</dd></div><div><dt>Строк с ошибками</dt><dd>{{value.summary.error_rows}}</dd></div><div><dt>Строк с предупреждениями</dt><dd>{{value.summary.warning_rows}}</dd></div><div><dt>Сохранён</dt><dd>{{importTime(value.created_at)}} · {{value.actor?.full_name||'Сотрудник не указан'}}</dd></div></dl><p class="muted compact">{{value.parser_version}} · SHA-256: <span class="source-hash">{{value.source_sha256}}</span></p></section>
  <p v-if="value?.source_origin==='google_csv'" data-google-provenance class="message">Снимок значений Google · {{value.source_observed_at?importTime(value.source_observed_at):'Время чтения не указано'}}. Исходные формулы и другие листы в CSV не входят.</p>
  <RouterLink v-if="value && session.journalApplicationEnabled" data-open-reconciliation class="button-primary align-start" :to="{path:`/imports/${value.id}/reconciliation`,query:{return:route.fullPath}}">{{session.canAny('imports.reconcile','imports.apply')?'Сверить и перенести':'Просмотреть сверку'}}</RouterLink>
  <section class="card stack-card"><h2>Строки первого листа</h2><form data-import-row-filters class="filter-grid" @submit.prevent="filter()"><label>Поиск<input v-model="filters.search" name="search" type="search"/></label><label>Замечания<select v-model="filters.severity" name="severity"><option value="">Все строки</option><option value="error">С ошибками</option><option value="warning">С предупреждениями</option><option value="info">С пояснениями</option></select></label><label>Состояние в источнике<select v-model="filters.state" name="state"><option value="">Все состояния</option><option v-for="(label,code) in importedStates" :key="code" :value="code">{{label}}</option></select></label><button type="submit" :disabled="rowsLoading">Применить</button></form><ApiMessage :error="rowError"/><button v-if="rowError" data-retry-import-rows :disabled="rowsLoading" @click="loadRows">Повторить загрузку строк</button><p v-if="rowsLoading" class="state">Загрузка строк…</p><div v-else-if="rows.results.length" class="table-scroll"><table><thead><tr><th>Строка / номер</th><th>Состояние</th><th>Специальность</th><th>Эксперт в источнике</th><th>Разбор</th></tr></thead><tbody><tr v-for="item in rows.results" :key="item.id"><td><button data-open-import-row @click="selected=item">Строка {{item.source_row}} · {{item.facts.registration_number||item.raw.B||'Номер не указан'}}</button></td><td>{{importedStates[String(item.facts.state)]||'Не распознано'}}</td><td>{{item.facts.specialty_code||'Не указана'}}</td><td>{{item.facts.executor_raw||'Не указан'}}</td><td>{{item.normalization_complete?'Разобрано':'Нужна проверка'}} · {{item.diagnostics.length}} замечаний</td></tr></tbody></table></div><p v-else-if="!rowError" class="state">Строк по выбранным условиям нет.</p><PaginationBar :page="currentPage" :count="rows.count" :next="Boolean(rows.next)" :previous="Boolean(rows.previous)" :busy="rowsLoading" @change="filter"/></section><ImportRowDetails v-if="selected" :row="selected"/>
</template></template>
<style scoped>.source-hash{overflow-wrap:anywhere}</style>
