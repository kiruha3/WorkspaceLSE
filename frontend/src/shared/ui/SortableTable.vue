<script setup lang="ts" generic="T">
import {computed,ref} from 'vue'
import {nextOrdering,sortRows,type SortColumn} from './tableSorting'
const props=defineProps<{rows:readonly T[];columns:readonly SortColumn<T>[];ordering?:string;pinFirst?:(row:T)=>boolean;busy?:boolean}>()
const emit=defineEmits<{'update:ordering':[value:string]}>()
const local=ref(''),current=computed(()=>props.ordering??local.value)
const shown=computed(()=>props.ordering===undefined?sortRows(props.rows,props.columns,current.value,props.pinFirst):props.rows)
function change(key:string){const next=nextOrdering(current.value,key);if(props.ordering===undefined)local.value=next;emit('update:ordering',next)}
function direction(key:string){return current.value===key?'ascending':current.value==='-'+key?'descending':'none'}
function hint(key:string){const next=nextOrdering(current.value,key);return !next?'Вернуть исходный порядок':next.startsWith('-')?'По убыванию':'По возрастанию'}
</script>
<template>
 <table class="sortable-table"><thead><tr><th v-for="column in columns" :key="column.key" :aria-sort="column.sortable===false?undefined:direction(column.key)">
  <button v-if="column.sortable!==false" type="button" class="table-sort-button" :data-sort-column="column.key" :title="hint(column.key)" :aria-label="`${column.label}: ${hint(column.key)}`" :disabled="busy" @click="change(column.key)"><span>{{column.label}}</span><span class="sort-arrow" :class="{'sort-active':direction(column.key)!=='none'}" :data-direction="direction(column.key)" aria-hidden="true" /></button>
  <template v-else>{{column.label}}</template><slot name="header-after" :column="column"/>
 </th></tr></thead><tbody><slot :rows="shown"/></tbody></table>
</template>
<style scoped>
.sortable-table .table-sort-button{display:inline-flex;align-items:center;gap:6px;min-height:24px;padding:0;border:0;border-radius:3px;background:transparent;color:inherit;font:inherit;text-align:left;line-height:1.4;white-space:normal}
.sortable-table .table-sort-button:hover:not(:disabled){background:transparent;color:var(--green);text-decoration:underline;text-underline-offset:3px}
.sort-arrow{flex-shrink:0;font-size:12px;font-weight:600;color:#9aa49a}.sort-active{color:var(--green)}
.sort-arrow::before{content:'↕'}.sort-arrow[data-direction=ascending]::before{content:'↑'}.sort-arrow[data-direction=descending]::before{content:'↓'}
@media(pointer:coarse){.sortable-table .table-sort-button{min-height:36px}}
</style>
