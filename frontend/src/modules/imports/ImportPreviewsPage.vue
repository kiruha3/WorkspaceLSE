<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import {orderingParams} from '../../shared/ui/tableSorting'
import {useRouteTableSort} from '../../shared/ui/useRouteTableSort'

import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { RouterLink,useRoute,useRouter } from 'vue-router'
import { LatestRequest,useApi } from '../../api/client'
import { importTime,type ImportBatch } from '../../api/imports'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import ImportUpload from './ImportUpload.vue'
import GooglePreview from './GooglePreview.vue'
const {ordering,sortTable}=useRouteTableSort()
const api=useApi(),session=useSessionStore(),route=useRoute(),router=useRouter(),requests=new LatestRequest()
const enabled=computed(()=>session.importPreviewEnabled&&session.can('imports.results.view')),canCreate=computed(()=>enabled.value&&session.can('imports.preview'))
const list=ref<Page<ImportBatch>>({count:0,next:null,previous:null,results:[]}),loading=ref(false),error=ref<unknown>(null),editing=ref(false),created=ref<ImportBatch|null>(null)
const currentPage=computed(()=>Math.max(1,Number(route.query.page)||1))
async function load(){
  if(!enabled.value)return
  loading.value=true;error.value=null;list.value={count:0,next:null,previous:null,results:[]}
  try{await requests.run(signal=>api.request<Page<ImportBatch>>(`/imports/?${new URLSearchParams({page:String(currentPage.value),...orderingParams(ordering.value)})}`,{signal}),value=>{list.value=value;loading.value=false})}catch(cause){error.value=cause;loading.value=false}
}
function saved(value:ImportBatch){editing.value=false;created.value=value;void load()}
function changePage(page:number){void router.replace({path:'/imports',query:{...orderingParams(ordering.value),page:String(page)}})}
watch([()=>route.fullPath,enabled],()=>{requests.cancel();if(enabled.value)void load();else list.value={count:0,next:null,previous:null,results:[]}},{immediate:true})
onBeforeUnmount(()=>requests.cancel())
</script>
<template>
  <p v-if="!enabled" class="state">Предпросмотр переноса недоступен в этой сессии.</p><template v-else><div class="page-heading"><div><p class="eyebrow">Подготовка исторического переноса</p><h1>Источники журнала</h1><p class="muted">Снимки первого листа, разобранные значения и места для проверки.</p></div><button v-if="canCreate&&!editing" data-new-import-preview class="button-primary" @click="editing=true">Проверить новый источник</button></div>
    <p class="message">Предпросмотр не меняет рабочие записи. Для переноса откройте снимок и отдельно подтвердите сопоставленный пакет. <RouterLink v-if="session.can('reports.form151.run')" to="/reports">Рассчитать предварительный 15.1 по снимку</RouterLink></p><section v-if="editing" class="card"><ImportUpload :can-create="canCreate" @created="saved" @cancel="editing=false"/></section><p v-if="created" data-preview-created class="message message-success">Снимок сохранён. <RouterLink :to="`/imports/${created.id}`">Открыть результат проверки</RouterLink></p>
    <GooglePreview v-if="session.googlePreviewEnabled" :can-create="canCreate" @created="saved"/>
    <ApiMessage :error="error"/><div class="button-row"><button :disabled="loading" @click="load">Обновить список снимков</button></div><p v-if="loading" class="state">Загрузка источников…</p><div v-else-if="list.results.length" class="table-scroll"><SortableTable :rows="list.results" :columns='[{"key": "source_name", "label": "Источник"}, {"key": "row_count", "label": "Строки"}, {"key": "errors", "label": "Ошибки"}, {"key": "warnings", "label": "Предупреждения"}, {"key": "created_at", "label": "Сохранён"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}"><tr v-for="item in tableRows" :key="item.id"><td><RouterLink data-open-import-preview :to="{path:`/imports/${item.id}`,query:{return:route.fullPath}}">{{item.source_name}}</RouterLink><small class="muted">{{item.sheet_name}} · {{item.parser_version}} · {{item.source_origin==='google_csv'?'Google · значения CSV':'Файл'}}</small></td><td>{{item.row_count}}</td><td>{{item.summary.error_rows}}</td><td>{{item.summary.warning_rows}}</td><td>{{importTime(item.created_at)}}<small>{{item.actor?.full_name||'Сотрудник не указан'}}</small></td></tr></SortableTable></div><p v-else-if="!error" class="state">Снимков пока нет. Загрузите источник для проверки, не изменяя рабочие экспертизы.</p><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="changePage"/>
  </template>
</template>
