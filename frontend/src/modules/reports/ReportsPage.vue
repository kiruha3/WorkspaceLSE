<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { RouterLink,useRoute } from 'vue-router'
import { LatestRequest,useApi } from '../../api/client'
import type { ImportBatch } from '../../api/imports'
import { importTime } from '../../api/imports'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

interface Cell { sheet:string; address:string; value:number|null; rows:number[] }
interface Report { status:string; version:string; year:number; month:number; from:string; to:string; source:{id:string;name:string;sha256:string;row_count:number;created_at:string}; download_url:string; cells:Cell[]; gaps:{code:string;sections:number[];message:string;fields:string;rows:number[]}[]; section_coverage:{section:number;filled:number;unavailable:number;status:string}[] }
const api=useApi(),session=useSessionStore(),route=useRoute(),requests=new LatestRequest(),sources=new LatestRequest()
// Sources are institution-wide, including old departments: a department grant
// cannot imply permission to calculate a mixed-source report.
const institution=(code:string)=>Boolean(session.user?.access[code]?.some(r=>r.scope==='institution'&&r.scope_limit==='institution'))
const enabled=computed(()=>institution('imports.results.view')&&institution('reports.form151.run'))
const canDownload=computed(()=>institution('reports.form151.download'))
const batches=ref<ImportBatch[]>([]),batchId=ref(''),year=ref(2026),month=ref(new Date().getMonth()+1),opening=ref(false)
const result=ref<Report|null>(null),loading=ref(false),loadingSources=ref(false),error=ref<unknown>(null),section=ref(1)
const months=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
const sections=[{id:1,name:'Экспертизы и исследования',columns:[['D','На начало'],['E','Поступило'],['F','СНДЗ'],['J','Заключения'],['K','Уголовные'],['L','Гражданские'],['M','Арбитражные'],['N','КоАП'],['O','КУСП'],['Q','На конец'],['R','Исследования на начало'],['S','Поступило исследований'],['T','Закончено исследований'],['U','Юрлица'],['V','Физлица'],['W','Иные лица'],['X','Исследования на конец']]},
  {id:2,name:'Вопросы',columns:[['D','Поставлено'],['E','Разрешено'],['F','Категорические'],['G','Вероятные'],['H','Не разрешено']]},
  {id:3,name:'Сроки',columns:[['D','До 30 дней'],['E','31–60 дней'],['F','От 61 дня']]},
  {id:4,name:'Сложность и возвраты',columns:[['D','1 категория'],['E','2 категория'],['F','3 категория'],['G','Выше 3'],['O','Возврат материалов']]},
  {id:5,name:'Органы назначения',columns:[['D','Экспертизы всего'],['E','Суды'],['F','СК РФ'],['G','МВД'],['H','ФСБ'],['I','ФТС'],['J','ФССП'],['K','Иные'],['L','Исследования всего'],['M','Исследования СК'],['N','Исследования МВД'],['O','Исследования ФСБ'],['P','Исследования ФТС'],['Q','Исследования ФССП'],['R','Исследования иные']]},
  {id:6,name:'Госзадание',columns:[['D','Годовой план'],['E','Выполнено'],['F','СНДЗ'],['G','Заключения'],['H','Уголовные'],['I','Гражданские'],['J','Арбитражные'],['K','КоАП'],['L','КУСП'],['M','Исследования']]}]
const active=computed(()=>sections.find(s=>s.id===section.value)!)
const rows=[{label:'Всего',base:108},{label:'1.1',base:11},{label:'3.1',base:14},{label:'13.1',base:50},{label:'16.1',base:59},{label:'16.2',base:60},{label:'18.1',base:65},{label:'19.1',base:67}]
const cellMap=computed(()=>new Map(result.value?.cells.map(c=>[`${c.sheet}!${c.address}`,c])??[]))
function cell(s:number,col:string,base=108){return cellMap.value.get(`Раздел ${s}!${col}${s===1||s===5?base:base-1}`)}
function show(value:number|null|undefined){return value==null?'—':value.toLocaleString('ru-RU')}
function trace(c:Cell|undefined){return c?.rows.length?`Строки источника: ${c.rows.join(', ')}`:'Нет участвующих строк'}
function invalidate(){requests.cancel();loading.value=false;result.value=null;error.value=null}
async function loadSources(){
  if(!enabled.value)return
  loadingSources.value=true;error.value=null
  try{await sources.run(signal=>api.allPages<ImportBatch>('/imports/',signal),value=>{
    batches.value=value
    batchId.value=value.find(b=>b.id===String(route.query.batch_id??''))?.id??value.find(b=>b.source_origin==='google_csv')?.id??value[0]?.id??''
    loadingSources.value=false
  })}catch(cause){error.value=cause;loadingSources.value=false}
}
async function calculate(){
  if(!enabled.value||!batchId.value)return
  result.value=null;error.value=null;loading.value=true
  const params=new URLSearchParams({batch_id:batchId.value,year:String(year.value),month:String(month.value),opening_balances_complete:String(opening.value)})
  try{await requests.run(signal=>api.request<Report>(`/reports/form151/?${params}`,{signal}),value=>{result.value=value;loading.value=false})}
  catch(cause){error.value=cause;loading.value=false}
}
watch([batchId,year,month,opening],invalidate)
watch(enabled,value=>{invalidate();sources.cancel();if(value)void loadSources();else{batches.value=[];loadingSources.value=false}},{immediate:true})
onBeforeUnmount(()=>{requests.cancel();sources.cancel()})
</script>
<template>
  <p v-if="!enabled" class="state">Для отчёта по общему журналу нужны права просмотра источника и расчёта 15.1 по учреждению.</p>
  <template v-else>
    <div class="page-heading"><div><p class="eyebrow">Отчётность учреждения</p><h1>Форма 15.1</h1><p class="muted">Предварительный расчёт по сохранённому журналу. Рабочие записи не изменяются.</p></div><RouterLink class="button" to="/imports">Источники журнала</RouterLink></div>
    <section class="card"><form class="report-form" @submit.prevent="calculate"><label>Снимок первого листа<select v-model="batchId" name="batch_id" required :disabled="loadingSources"><option v-for="b in batches" :key="b.id" :value="b.id">{{b.source_name}} · {{b.row_count}} записей · {{importTime(b.created_at)}}</option></select></label><label>Год<input v-model.number="year" name="year" type="number" min="1900" max="2200" required/></label><label>По месяц включительно<select v-model.number="month" name="month"><option v-for="(m,i) in months" :key="m" :value="i+1">{{m}}</option></select></label><label class="coverage-check"><input v-model="opening" name="opening_balances_complete" type="checkbox"/>Подтверждаю полноту журнала для расчёта остатков на начало и конец периода</label><div class="button-row"><button class="button-primary" :disabled="loading||loadingSources||!batchId">{{loading?'Расчёт…':'Рассчитать 15.1'}}</button></div></form><p class="muted">Период накопительный: с 1 января до конца выбранного месяца. План 2026 — 294, госзадание — категории 1 и 5.</p><p v-if="!loadingSources&&!batches.length" class="message">Снимков ещё нет. Сначала сохраните источник в разделе «Источники журнала».</p></section>
    <ApiMessage :error="error"/>
    <p v-if="loading" class="state" role="status">Сервер рассчитывает показатели и проверяет пробелы…</p>
    <div v-if="result" data-report-result>
      <section class="card report-summary"><div><p class="eyebrow">Предварительный отчёт</p><h2>{{result.from}} — {{result.to}}</h2><p>{{result.source.row_count}} регистраций · {{result.source.name}}</p><small class="muted">{{result.version}} · снимок {{importTime(result.source.created_at)}} · SHA256 {{result.source.sha256.slice(0,12)}}</small></div><a v-if="canDownload" data-download-report class="button button-primary" :href="result.download_url" download>Скачать 15.1 в Excel</a><p v-else class="muted">Для скачивания нужно отдельное право выгрузки 15.1.</p></section>
      <p class="message">Выгрузка сохраняет исходный бланк. Прочерк в вебе — неизвестный показатель, в Excel он остаётся пустым. Причины, повторность, 3214-р и разделы 7–8 не подтверждены этим источником.</p>
      <div class="report-totals"><section class="card"><small>Заключений эксперта</small><strong>{{show(cell(1,'J')?.value)}}</strong></section><section class="card"><small>Сообщений СНДЗ</small><strong>{{show(cell(1,'F')?.value)}}</strong></section><section class="card"><small>Исследований закончено</small><strong>{{show(cell(1,'T')?.value)}}</strong></section><section class="card"><small>Госзадание выполнено</small><strong>{{show(cell(6,'E')?.value)}}</strong></section></div>
      <section class="card"><h2>Разделы 1–6</h2><div class="button-row" aria-label="Раздел отчёта"><button v-for="s in sections" :key="s.id" :class="{'button-primary':section===s.id}" @click="section=s.id">{{s.id}}. {{s.name}}</button></div><p class="muted">{{active.name}}. В таблице показаны специальности журнала и общий итог. В Excel также сохранены родительские строки бланка. Наведите на число, чтобы увидеть строки источника.</p><div class="table-scroll"><table><thead><tr><th>Специальность</th><th v-for="column in active.columns" :key="column[0]">{{column[1]}}</th></tr></thead><tbody><tr v-for="r in rows" :key="r.base" :class="{'report-total-row':r.base===108}"><th>{{r.label}}</th><td v-for="column in active.columns" :key="column[0]" :title="trace(cell(section,column[0]!,r.base))">{{show(cell(section,column[0]!,r.base)?.value)}}</td></tr></tbody></table></div></section>
      <section class="card"><h2>Что осталось уточнить</h2><p class="muted">Это список недостающих данных, а не препятствие для предварительной выгрузки. Она не означает готовность к официальной сдаче.</p><details v-for="g in result.gaps" :key="g.code" class="report-gap"><summary>Разделы {{g.sections.join(', ')}} · {{g.message}} <span v-if="g.rows.length">({{g.rows.length}} регистраций)</span></summary><p class="muted">{{g.fields}}</p><p v-if="g.rows.length">Строки первого листа: {{g.rows.join(', ')}}</p></details><RouterLink :to="`/imports/${result.source.id}`">Открыть снимок и исходные строки</RouterLink></section>
    </div>
  </template>
</template>
<style scoped>
.report-form{display:grid;grid-template-columns:minmax(240px,2fr) 110px minmax(180px,1fr);gap:18px}.report-form label{display:flex;flex-direction:column;gap:7px}.report-form .coverage-check{grid-column:1/-1;flex-direction:row;align-items:center}.coverage-check input{width:18px;height:18px;flex-shrink:0}.report-summary{display:flex;gap:24px;align-items:center;justify-content:space-between}.report-summary h2{margin:4px 0}.report-summary .button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 18px;border-radius:8px;white-space:nowrap;text-decoration:none}.report-totals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:20px 0}.report-totals strong{display:block;font-size:30px;margin-top:12px}.report-gap{padding:14px 0;border-bottom:1px solid var(--border,#dde3dc)}.report-gap summary{cursor:pointer;line-height:1.6}.report-total-row{font-weight:700;background:#edf3e9}td{text-align:right}th{white-space:normal;min-width:100px}.card{margin-bottom:20px}@media(max-width:900px){.report-form{grid-template-columns:1fr}.report-totals{grid-template-columns:repeat(2,1fr)}.report-summary{align-items:flex-start;flex-direction:column}}
</style>
