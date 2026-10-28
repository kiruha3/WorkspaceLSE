<script setup lang="ts">
import type { FactRevision } from '../api/types'
defineProps<{revisions:FactRevision[];labels?:Record<string,string>;formatValue?:(key:string,value:unknown)=>string}>()
function show(value:unknown):string {
 if(value==null||value==='')return 'Неизвестно'
 if(typeof value==='boolean')return value?'Да':'Нет'
 if(typeof value==='object')return 'name' in value?String(value.name):JSON.stringify(value)
 return String(value)
}
function changed(item:FactRevision){
 const before=item.before??item.changes?.before??{},after=item.after??item.changes?.after??item.changes??{}
 const left=before as Record<string,unknown>,right=after as Record<string,unknown>
 return Object.keys(right).filter(key=>JSON.stringify(left[key])!==JSON.stringify(right[key])).map(key=>({key,before:left[key],after:right[key]}))
}
const time=(value:string)=>new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Krasnoyarsk',dateStyle:'short',timeStyle:'short'}).format(new Date(value))
</script>
<template><section class="subsection"><h3>История изменений</h3><details v-for="item in revisions" :key="item.id"><summary>{{item.number?`№${item.number} · `:''}}{{item.actor?.full_name??'Система'}} · {{time(item.created_at)}}</summary><p>{{item.reason||'Основание не указано'}}</p><div class="table-scroll"><table><thead><tr><th>Сведение</th><th>Было</th><th>Стало</th></tr></thead><tbody><tr v-for="change in changed(item)" :key="change.key"><th>{{labels?.[change.key]??change.key}}</th><td>{{formatValue?formatValue(change.key,change.before):show(change.before)}}</td><td>{{formatValue?formatValue(change.key,change.after):show(change.after)}}</td></tr></tbody></table></div></details><p v-if="!revisions.length" class="muted compact">Изменений пока нет.</p></section></template>
<style scoped>details{padding:14px 0;border-top:1px solid var(--border)}summary{cursor:pointer;line-height:1.6}td{white-space:pre-wrap;overflow-wrap:anywhere;max-width:420px;vertical-align:top}</style>
