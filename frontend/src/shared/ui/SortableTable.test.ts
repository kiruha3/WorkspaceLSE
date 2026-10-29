import {mount} from '@vue/test-utils'
import {describe,expect,it} from 'vitest'
import SortableTable from './SortableTable.vue'
import {sortRows} from './tableSorting'

const rows=[{id:'a',value:'10/4-1-26'},{id:'b',value:'2/4-1-26'},{id:'c',value:null},{id:'d',value:'2/4-1-26'}]
const columns=[{key:'value',label:'Номер',value:(row:typeof rows[number])=>row.value}]
describe('table sorting',()=>{
 it('sorts dates by time and pins the report total while leaving empty cells last',()=>{
  const data=[{id:'total',value:50},{id:'unknown',value:null},{id:'low',value:2},{id:'high',value:10}]
  expect(sortRows(data,[{key:'value',label:'Объём'}],'-value',row=>row.id==='total').map(row=>row.id)).toEqual(['total','high','low','unknown'])
  const dates=[{value:new Date('2026-12-01')},{value:new Date('2026-01-31')}]
  expect(sortRows(dates,[{key:'value',label:'Дата'}],'value')[0]).toBe(dates[1])
  const compound=[{id:'missing',value:[null,'a']},{id:'known',value:['Я','b']}]
  expect(sortRows(compound,[{key:'value',label:'Состав'}],'-value').map(row=>row.id)).toEqual(['known','missing'])
 })
 it('compares numeric parts naturally, keeps ties stable and leaves blanks last in both directions',()=>{
  expect(sortRows(rows,columns,'value').map(row=>row.id)).toEqual(['b','d','a','c'])
  expect(sortRows(rows,columns,'-value').map(row=>row.id)).toEqual(['a','b','d','c'])
  expect(sortRows(rows,columns,'').map(row=>row.id)).toEqual(['a','b','c','d'])
  expect(rows.map(row=>row.id)).toEqual(['a','b','c','d'])
 })
 it('cycles a header through ascending, descending and original rows and keeps actions unsortable',async()=>{
  const wrapper=mount(SortableTable<typeof rows[number]>,{props:{rows,columns:[...columns,{key:'actions',label:'Действия',sortable:false}]},slots:{default:'<template #default="{rows}"><tr v-for="row in rows" :key="row.id"><td>{{row.id}}</td></tr></template>'}})
  const heading=wrapper.get('thead button')
  const ids=()=>wrapper.findAll('tbody td').map(td=>td.text())
  expect(wrapper.findAll('thead button')).toHaveLength(1)
  expect(wrapper.get('th').attributes('aria-sort')).toBe('none')
  await heading.trigger('click');expect(ids()).toEqual(['b','d','a','c']);expect(wrapper.get('th').attributes('aria-sort')).toBe('ascending')
  await heading.trigger('click');expect(ids()).toEqual(['a','b','d','c']);expect(wrapper.get('th').attributes('aria-sort')).toBe('descending')
  await heading.trigger('click');expect(ids()).toEqual(['a','b','c','d']);expect(wrapper.get('th').attributes('aria-sort')).toBe('none')
 })
 it('emits server ordering without sorting a partial page and switches a new column to ascending',async()=>{
  const wrapper=mount(SortableTable<typeof rows[number]>,{props:{rows,columns:[...columns,{key:'id',label:'Код'}],ordering:'-value'},slots:{default:'<template #default="{rows}"><tr v-for="row in rows" :key="row.id"><td>{{row.id}}</td></tr></template>'}})
  await wrapper.get('[data-sort-column="value"]').trigger('click')
  expect(wrapper.emitted('update:ordering')?.[0]).toEqual([''])
  expect(wrapper.findAll('tbody td').map(td=>td.text())).toEqual(['a','b','c','d'])
  await wrapper.get('[data-sort-column="id"]').trigger('click')
  expect(wrapper.emitted('update:ordering')?.[1]).toEqual(['id'])
 })
})
