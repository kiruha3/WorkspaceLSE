<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import HelpTip from '../../shared/ui/HelpTip.vue'
import type { HistoricalWork } from '../../api/types'
import BasisPreview from '../../shared/BasisPreview.vue'
defineProps<{history:HistoricalWork}>()
const labels:Record<string,string>={specialty:'Специальность',result_kind:'Вид результата',completed_on:'Дата окончания',return_decided_on:'Дата решения',complexity_level:'Сложность',questions:'Поставлено вопросов',categorical:'Категорические ответы',probable:'Вероятные ответы',unresolved:'Не разрешено',statistics_confirmed:'Полнота статистики',sndz_reason:'Причина СНДЗ',sndz_comment:'Пояснение СНДЗ',allocations_complete:'Полнота распределения T',unresolved_allocations:'Причины нерешённых вопросов',report_note:'Примечание',return_reason:'Причина без исполнения',return_comment:'Пояснение к решению'}
const kinds:Record<string,string>={expert_conclusion:'Заключение эксперта',sndz:'СНДЗ',research_act:'Акт исследования'}
function show(value:unknown):string{
 if(value===null||value===undefined||value==='')return 'Неизвестно'
 if(typeof value==='boolean')return value?'Да':'Нет'
 if(Array.isArray(value))return value.map(v=>`${show(v.reason)}: ${v.count}${v.comment?` (${v.comment})`:''}`).join('; ')||'Нет распределения'
 if(typeof value==='object'&&'code' in value&&'name' in value)return `${value.code} · ${value.name}`
 return kinds[String(value)]??String(value)
}
function changes(c:NonNullable<HistoricalWork['corrections']>[number]){return Object.keys(c.after).filter(key=>JSON.stringify(c.before[key])!==JSON.stringify(c.after[key])).map(key=>({key,before:c.before[key],after:c.after[key]}))}
function time(value:string){return new Intl.DateTimeFormat('ru-RU',{timeZone:'Asia/Krasnoyarsk',dateStyle:'short',timeStyle:'short'}).format(new Date(value))}
</script>
<template>
 <div v-if="history.report_details" class="subsection">
  <p v-if="history.result_kind==='sndz'">Причина полного СНДЗ: {{history.report_details.sndz_reason?.name??'Неизвестно'}}. {{history.report_details.sndz_comment}}</p>
  <p v-if="history.report_details.return_reason||history.return_decided_on">Причина решения без исполнения: {{history.report_details.return_reason?.name??'Неизвестно'}}. {{history.report_details.return_comment}}</p>
  <div v-for="item in history.report_details.unresolved_allocations" :key="item.reason.id"><p>{{item.reason.name}}: {{item.count}}. {{item.comment}}</p><BasisPreview v-if="item.document" :document="item.document" heading="Подтверждающий документ"/></div>
  <p class="muted compact">Распределение T: {{history.report_details.allocations_complete?'подтверждено':'не подтверждено'}}.</p>
  <p v-if="history.report_details.note">{{history.report_details.note}}</p>
 </div>
 <section data-history-corrections class="subsection"><h3>История уточнений</h3>
  <details v-for="c in history.corrections??[]" :key="c.id" class="correction"><summary>№{{c.number}} · {{c.actor.full_name}} · {{time(c.created_at)}}</summary>
   <p>{{c.reason}}</p><div class="table-scroll"><SortableTable :rows="changes(c)" :columns="[{key:'field',label:'Сведение',value:r=>labels[r.key]??r.key},{key:'before',label:'Было',value:r=>show(r.before)},{key:'after',label:'Стало',value:r=>show(r.after)}]" v-slot="{rows:tableRows}"><tr v-for="change in tableRows" :key="change.key"><th>{{labels[change.key]??change.key}}</th><td>{{show(change.before)}}</td><td>{{show(change.after)}}</td></tr></SortableTable></div>
  </details><p v-if="!history.corrections?.length" class="muted compact">Ручных уточнений пока нет. <HelpTip label="История уточнений">Исходный снимок сохраняется отдельно.</HelpTip></p>
 </section>
</template>
<style scoped>.correction{padding:14px 0;border-top:1px solid var(--border)}summary{cursor:pointer;line-height:1.6}td{white-space:pre-wrap;overflow-wrap:anywhere;max-width:420px;vertical-align:top}th{min-width:130px}</style>
