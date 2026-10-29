<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import {orderingParams} from '../../shared/ui/tableSorting'

import { computed,onBeforeUnmount,ref } from 'vue'
import { LatestRequest,useApi } from '../../api/client'
import type { FactRevision,Page,Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import FactHistory from '../../shared/FactHistory.vue'
import ReferenceEditor from './ReferenceEditor.vue'
import { catalogs,closureRules,reportGroups } from './catalogs'
const ordering=ref('')
function sortTable(value:string){ordering.value=value;page.value=1;void load()}
const session=useSessionStore(),api=useApi(),requests=new LatestRequest(),historyRequest=new LatestRequest(),editorRequest=new LatestRequest()
const catalog=ref('departments'),search=ref(''),active=ref(''),page=ref(1),listing=ref<Page<Reference>|null>(null),loading=ref(false),error=ref<unknown>(null),success=ref('')
const editing=ref(false),item=ref<Reference|null>(null),editor=ref<InstanceType<typeof ReferenceEditor>|null>(null)
const history=ref<FactRevision[]|null>(null),historyTitle=ref(''),historyError=ref<unknown>(null),historyLoading=ref(false)
const title=computed(()=>catalogs.find(([key])=>key===catalog.value)?.[1]??'Справочник')
async function load(){loading.value=true;error.value=null;const query=new URLSearchParams({page:String(page.value),...orderingParams(ordering.value)});if(search.value.trim())query.set('search',search.value.trim());if(active.value)query.set('is_active',active.value)
 try{await requests.run(signal=>api.request<Page<Reference>>(`/references/${catalog.value}/?${query}`,{signal}),value=>{listing.value=value;loading.value=false;if(item.value){const refreshed=value.results.find(entry=>entry.id===item.value?.id);if(refreshed)item.value=refreshed}})}catch(cause){error.value=cause;loading.value=false}}
function changeCatalog(event:Event){const element=event.target as HTMLSelectElement;if(editor.value&&!editor.value.confirmLeave()){element.value=catalog.value;return}catalog.value=element.value;editing.value=false;item.value=null;listing.value=null;editorRequest.cancel();historyRequest.cancel();history.value=null;historyTitle.value='';historyLoading.value=false;search.value='';active.value='';page.value=1;success.value='';void load()}
function start(entry:Reference|null){if(editor.value&&!editor.value.confirmLeave())return;item.value=entry;editing.value=true}
function saved(entry:Reference){editing.value=false;item.value=null;success.value=`Сохранено: ${entry.name}. Код ${entry.code}.`;history.value=null;void load()}
async function refreshItem(){
 if(!item.value)return
 const id=item.value.id,code=item.value.code;error.value=null
 try{await editorRequest.run(signal=>api.allPages<Reference>(`/references/${catalog.value}/?search=${encodeURIComponent(code)}`,signal),items=>{const current=items.find(entry=>entry.id===id);if(item.value?.id===id&&current)item.value=current})}catch(cause){error.value=cause}
}
async function showHistory(entry:Reference){historyTitle.value=entry.name;history.value=null;historyError.value=null;historyLoading.value=true;try{await historyRequest.run(signal=>api.request<FactRevision[]>(`/references/${catalog.value}/${entry.id}/history/`,{signal}),value=>{history.value=value;historyLoading.value=false})}catch(cause){historyError.value=cause;historyLoading.value=false}}
function subtype(entry:Reference){if(entry.report_group!==undefined)return reportGroups.find(([code])=>code===entry.report_group)?.[1]??'Группа не определена';if(entry.direction)return `${entry.direction==='incoming'?'Входящие':'Исходящие'} · ${entry.department_id?'Отдел: '+entry.department_id:'Общий журнал'}`;if(entry.rule)return closureRules.find(([code])=>code===entry.rule)?.[1]??entry.rule;return ''}
onBeforeUnmount(()=>{requests.cancel();historyRequest.cancel();editorRequest.cancel()});void load()
</script>
<template><div class="page-heading"><div><p class="eyebrow">Настройка учреждения</p><h1>Справочники</h1><p class="muted">Единые значения для карточек, переписки, выдачи и отчётов. Старые ссылки сохраняются после деактивации.</p></div><span class="badge">{{session.can('references.manage')?'Управление':'Только просмотр'}}</span></div>
 <ApiMessage :error="error"/><p v-if="success" class="message message-success" role="status">{{success}}</p>
 <section class="card form-grid"><label>Справочник<select name="catalog" :value="catalog" @change="changeCatalog"><option v-for="[code,label] in catalogs" :key="code" :value="code">{{label}}</option></select></label><form data-reference-search class="toolbar" @submit.prevent="page=1;load()"><label>Поиск по коду или названию<input v-model="search" name="reference_search" type="search"/></label><label>Активность<select v-model="active" name="reference_filter_active"><option value="">Все записи</option><option value="true">Активные</option><option value="false">Неактивные</option></select></label><button>Найти</button></form></section>
 <ReferenceEditor v-if="editing" :key="`${catalog}-${item?.id??'new'}`" ref="editor" :catalog="catalog" :item="item" @saved="saved" @cancel="editing=false;item=null" @refresh="refreshItem"/>
 <section class="card stack-card"><div class="section-heading"><h2>{{title}}</h2><button v-if="session.can('references.manage')" data-reference-create class="button-primary" @click="start(null)">Добавить запись</button></div><p v-if="loading" role="status">Загрузка справочника…</p><button v-if="error" @click="load">Повторить загрузку</button><div v-if="listing" class="table-scroll"><SortableTable :rows="listing.results" :columns='[{"key": "code", "label": "Код"}, {"key": "name", "label": "Название"}, {"key": "is_active", "label": "Состояние / правило"}, {"key": "actions", "label": "Действия", "sortable": false}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}"><tr v-for="entry in tableRows" :key="entry.id"><td>{{entry.code}}</td><td>{{entry.name}}</td><td><span class="badge" :class="entry.is_active?'badge-green':''">{{entry.is_active?'Активна':'Неактивна'}}</span><small>{{subtype(entry)}}</small></td><td><div class="button-row"><button v-if="session.can('references.manage')" data-reference-edit @click="start(entry)">Редактировать</button><button data-reference-history @click="showHistory(entry)">История</button></div></td></tr></SortableTable><p v-if="!listing.results.length" class="state">Записей по заданным условиям нет.</p></div><div v-if="listing" class="button-row"><button :disabled="!listing.previous||loading" @click="page--;load()">← Назад</button><span>Страница {{page}} · записей {{listing.count}}</span><button :disabled="!listing.next||loading" @click="page++;load()">Далее →</button></div></section>
 <section v-if="historyTitle" class="card stack-card"><h2>{{historyTitle}}</h2><ApiMessage :error="historyError"/><p v-if="historyLoading" role="status">Загрузка истории…</p><FactHistory v-if="history" :revisions="history" :labels="{name:'Название',is_active:'Активность',code:'Код',report_group:'Группа для отчёта'}"/></section>
</template>
<style scoped>td{vertical-align:top;white-space:normal;overflow-wrap:anywhere;max-width:450px}small{display:block;margin-top:7px}.toolbar{display:flex;flex-wrap:wrap;gap:14px;align-items:end}.toolbar label{flex:1;min-width:180px}</style>
