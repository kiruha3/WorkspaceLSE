<script setup lang="ts">
import { computed,onBeforeUnmount,ref,watch } from 'vue'
import { RouterLink,useRoute } from 'vue-router'
import { LatestRequest,useApi } from '../../api/client'
import type { ImportBatch } from '../../api/imports'
import { importTime } from '../../api/imports'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

interface Cell { sheet:string; address:string; value:number|null; rows:(number|string)[] }
interface WorkReference { id:string; registration_number:string }
interface ColumnRule { section:number; column:string; official_column:number; meaning:string; unit:string; sources:string[]; period:string; unknown:string[]; limitations:string[] }
interface Report { status:string; version:string; delay_reason_policy?:'all'|'primary'|null; rules_version?:string;column_rules?:ColumnRule[]; year:number; month:number; from:string; to:string; source:{type?:'journal'|'registry';id:string|null;name:string;sha256?:string;row_count:number;created_at?:string;calculated_at?:string;data_revision?:string;excluded_demo_count?:number}; records?:Record<string,WorkReference>; download_url:string; cells:Cell[]; gaps:{code:string;sections:number[];message:string;fields:string;rows:(number|string)[]}[]; section_coverage:{section:number;filled:number;unavailable:number;status:string}[] }
const api=useApi(),session=useSessionStore(),route=useRoute(),requests=new LatestRequest(),sources=new LatestRequest(),downloads=new LatestRequest()
// Sources are institution-wide, including old departments: a department grant
// cannot imply permission to calculate a mixed-source report.
const institution=(code:string)=>Boolean(session.user?.access[code]?.some(r=>r.scope==='institution'&&r.scope_limit==='institution'))
const mode=ref<'journal'|'registry'>(route.query.batch_id?'journal':'registry')
const enabled=computed(()=>institution(mode.value==='registry'?'expertise.view':'imports.results.view')&&institution('reports.form151.run'))
const canDownload=computed(()=>institution('reports.form151.download'))
const batches=ref<ImportBatch[]>([]),batchId=ref(''),year=ref(2026),month=ref(new Date().getMonth()+1),opening=ref(false)
const delayPolicy=ref<'all'|'primary'>('all')
const delayPolicyLabels={all:'По всем указанным причинам',primary:'Только по основной причине'}
const result=ref<Report|null>(null),loading=ref(false),loadingSources=ref(false),error=ref<unknown>(null),section=ref(1)
const downloading=ref(false),downloadError=ref<unknown>(null),selectedCell=ref<Cell|null>(null)
const selectedRule=ref<{section:number;column:string}|null>(null)
const rule=computed(()=>result.value?.column_rules?.find(r=>r.section===selectedRule.value?.section&&r.column===selectedRule.value?.column))
const months=['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
const sections=[{id:1,name:'Экспертизы и исследования',columns:[['D','На начало'],['E','Поступило'],['F','СНДЗ'],['J','Заключения'],['K','Уголовные'],['L','Гражданские'],['M','Арбитражные'],['N','КоАП'],['O','КУСП'],['Q','На конец'],['R','Исследования на начало'],['S','Поступило исследований'],['T','Закончено исследований'],['U','Юрлица'],['V','Физлица'],['W','Иные лица'],['X','Исследования на конец']]},
  {id:2,name:'Вопросы',columns:[['D','Поставлено'],['E','Разрешено'],['F','Категорические'],['G','Вероятные'],['H','Не разрешено']]},
  {id:3,name:'Сроки',columns:[['D','До 30 дней'],['E','31–60 дней'],['F','От 61 дня']]},
  {id:4,name:'Сложность и возвраты',columns:[['D','1 категория'],['E','2 категория'],['F','3 категория'],['G','Выше 3'],['O','Возврат материалов']]},
  {id:5,name:'Органы назначения',columns:[['D','Экспертизы всего'],['E','Суды'],['F','СК РФ'],['G','МВД'],['H','ФСБ'],['I','ФТС'],['J','ФССП'],['K','Иные'],['L','Исследования всего'],['M','Исследования СК'],['N','Исследования МВД'],['O','Исследования ФСБ'],['P','Исследования ФТС'],['Q','Исследования ФССП'],['R','Исследования иные']]},
  {id:6,name:'Госзадание',columns:[['D','Годовой план'],['E','Выполнено'],['F','СНДЗ'],['G','Заключения'],['H','Уголовные'],['I','Гражданские'],['J','Арбитражные'],['K','КоАП'],['L','КУСП'],['M','Исследования']]}]
const reasonColumns:Record<number,string[][]>={
  1:[['G','СНДЗ: вне специальных знаний'],['H','СНДЗ: материалы непригодны / недостаточны, отказано в дополнении'],['I','СНДЗ: уровень науки'],['P','В рамках 3214-р']],
  2:[['I','Недостаточная разработанность методик'],['J','Недостаточность материалов'],['K','Недостаточная информативность объектов'],['L','Иные причины вопросов']],
  3:[['G','Сложность исследований'],['H','Объём материалов'],['I','Загруженность экспертов'],['J','Длительные методики'],['K','Срок назначившего органа'],['L','Иные причины длительности'],['M','Информирование и ходатайство'],['N','Подтверждённое нарушение срока']],
  4:[['H','Повторных всего'],['I','После СЭУ Минюста'],['J','Из них: выводы не подтверждены (Минюст)'],['K','После иных государственных СЭУ'],['L','Из них: выводы не подтверждены (иные гос.)'],['M','После иных организаций / экспертов'],['N','Из них: выводы не подтверждены (иные)'],['P','Нет материально-технической базы'],['Q','Нет эксперта специальности'],['R','Нет специальных условий'],['S','По запросу назначившего органа'],['T','Иные причины возврата']],
}
const active=computed(()=>{
  const base=sections.find(s=>s.id===section.value)!
  return result.value?.source.type==='registry'?{...base,columns:[...base.columns,...(reasonColumns[base.id]??[])].sort((a,b)=>a[0]!.localeCompare(b[0]!))}:base
})
const rows=[{label:'Всего',base:108},{label:'1.1',base:11},{label:'3.1',base:14},{label:'13.1',base:50},{label:'16.1',base:59},{label:'16.2',base:60},{label:'18.1',base:65},{label:'19.1',base:67}]
const cellMap=computed(()=>new Map(result.value?.cells.map(c=>[`${c.sheet}!${c.address}`,c])??[]))
function cell(s:number,col:string,base=108){return cellMap.value.get(`Раздел ${s}!${col}${s===1||s===5?base:base-1}`)}
function show(value:number|null|undefined){return value==null?'—':value.toLocaleString('ru-RU')}
function work(id:number|string){return result.value?.records?.[String(id)]}
function trace(c:Cell|undefined){return c?.rows.length?(result.value?.source.type==='registry'?'Экспертизы: ':'Строки источника: ')+c.rows.map(id=>work(id)?.registration_number??id).join(', '):'Нет участвующих записей'}
function invalidate(){requests.cancel();downloads.cancel();loading.value=false;downloading.value=false;result.value=null;selectedCell.value=null;selectedRule.value=null;error.value=null;downloadError.value=null}
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
  if(!enabled.value||(mode.value==='journal'&&!batchId.value))return
  invalidate();loading.value=true
  const params=new URLSearchParams(mode.value==='registry'?{source:'registry'}:{batch_id:batchId.value})
  params.set('year',String(year.value));params.set('month',String(month.value));params.set('opening_balances_complete',String(opening.value))
  if(mode.value==='registry')params.set('delay_reason_policy',delayPolicy.value)
  try{await requests.run(signal=>api.request<Report>(`/reports/form151/?${params}`,{signal}),value=>{result.value=value;loading.value=false})}
  catch(cause){error.value=cause;loading.value=false}
}
async function download(){
  if(!result.value||downloading.value||!canDownload.value)return
  downloading.value=true;downloadError.value=null
  const path=result.value.download_url.replace(/^\/api\/v1/,'')
  try{await downloads.run(signal=>api.download(path,signal),file=>{
    const url=URL.createObjectURL(file.blob),link=document.createElement('a')
    link.href=url;link.download=file.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
    downloading.value=false
  })}catch(cause){downloadError.value=cause;downloading.value=false}
}
watch([batchId,year,month,opening,delayPolicy],invalidate)
watch(section,()=>{selectedRule.value=null;selectedCell.value=null})
watch([mode,enabled],([,value])=>{invalidate();sources.cancel();loadingSources.value=false;if(value&&mode.value==='journal')void loadSources()},{immediate:true})
onBeforeUnmount(()=>{requests.cancel();sources.cancel();downloads.cancel()})
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Отчётность учреждения</p><h1>Форма 15.1</h1><p class="muted">Рабочие записи АИС или сохранённый снимок для сравнения. Расчёт не изменяет данные.</p></div><RouterLink class="button" to="/expertises">Реестр экспертиз</RouterLink></div>
  <section class="card"><label>Источник расчёта<select v-model="mode" name="report_source"><option value="registry">Рабочая база АИС</option><option value="journal">Снимок первого листа</option></select></label></section>
  <p v-if="!enabled" class="state">Нужны права расчёта 15.1 и просмотра выбранного источника по учреждению: экспертиз для рабочей базы или источников журнала для снимка.</p>
  <template v-else>
    <section class="card">
      <form class="report-form" @submit.prevent="calculate">
        <label v-if="mode==='journal'">Снимок первого листа<select v-model="batchId" name="batch_id" required :disabled="loadingSources"><option v-for="b in batches" :key="b.id" :value="b.id">{{b.source_name}} · {{b.row_count}} записей · {{importTime(b.created_at)}}</option></select></label>
        <label>Год<input v-model.number="year" name="year" type="number" min="1900" max="2200" required/></label>
        <label>По месяц включительно<select v-model.number="month" name="month"><option v-for="(m,i) in months" :key="m" :value="i+1">{{m}}</option></select></label>
        <label v-if="mode==='registry'">Причины длительности · раздел 3<select v-model="delayPolicy" name="delay_reason_policy" aria-describedby="delay-policy-help"><option value="all">По всем указанным причинам</option><option value="primary">Только по основной причине</option></select></label>
        <label class="coverage-check"><input v-model="opening" name="opening_balances_complete" type="checkbox"/>Подтверждаю полноту выбранного набора для расчёта остатков на начало и конец периода</label>
        <div class="button-row"><button class="button-primary" :disabled="loading||loadingSources||(mode==='journal'&&!batchId)">{{loading?'Расчёт…':'Рассчитать 15.1'}}</button></div>
      </form>
      <p v-if="mode==='registry'" id="delay-policy-help" class="muted">По всем причинам: одна экспертиза учитывается один раз в каждой указанной группе причин. Только по основной: учитывается одна группа; если она не определена однозначно, зависимые значения остаются неизвестными. Режим применяется только к графам причин длительности раздела 3 и сохраняется в выгрузке Excel.</p>
      <p class="muted">Период накопительный: с 1 января до конца выбранного месяца. План 2026 — 294, госзадание — категории 1 и 5.</p>
      <p v-if="mode==='registry'" class="muted">Принятый результат имеет приоритет над историей; черновики и явно учебные материалы в отчёт не включаются. Выдача не заменяет решение без исполнения.</p>
      <p v-else-if="!loadingSources&&!batches.length" class="message">Снимков ещё нет. Сначала сохраните источник в разделе «Источники журнала».</p>
    </section>
    <ApiMessage :error="error"/>
    <p v-if="loading" class="state" role="status">Сервер рассчитывает показатели и проверяет пробелы…</p>
    <div v-if="result" data-report-result>
      <section class="card report-summary"><div><p class="eyebrow">Предварительный отчёт</p><h2>{{result.from}} — {{result.to}}</h2><p>{{result.source.row_count}} регистраций в наборе · {{result.source.name}}</p><small v-if="result.source.type==='registry'" class="muted">Расчёт {{importTime(result.source.calculated_at!)}} · редакция {{result.source.data_revision?.slice(0,12)}} · Учебных работ исключено: {{result.source.excluded_demo_count}}</small><small v-else class="muted">Снимок {{importTime(result.source.created_at!)}} · SHA256 {{result.source.sha256?.slice(0,12)}}</small><small class="muted">{{result.version}}</small></div><button v-if="canDownload" data-download-report class="button-primary" :disabled="downloading" @click="download">{{downloading?'Подготовка Excel…':'Скачать 15.1 в Excel'}}</button><p v-else class="muted">Для скачивания нужно отдельное право выгрузки 15.1.</p></section>
      <p v-if="result.source.type==='registry'" data-result-delay-policy class="message">Причины длительности · {{result.delay_reason_policy?delayPolicyLabels[result.delay_reason_policy]:'Режим не указан сервером — повторите расчёт после обновления приложения.'}}</p>
      <div v-if="downloadError" class="message message-error" role="alert"><strong>Выгрузка не выполнена</strong><p>{{downloadError instanceof Error?downloadError.message:'Повторите расчёт и скачивание.'}}</p><p>Файл не сохранён. При изменении данных нужно снова нажать «Рассчитать 15.1».</p></div>
      <p class="message">Исходный бланк сохраняется. Прочерк означает неизвестное значение и остаётся пустым в Excel. <template v-if="result.source.type==='registry'">Причины СНДЗ, нерешённых вопросов и возврата берутся из принятого результата или решения; 3214-р — из подтверждённых сведений дела. Повторность — из классификации и предыдущих заключений; для полного СНДЗ правило повторности пока не установлено. Причины длительности, информирование, ходатайство и оценка нарушения срока — из подтверждённых фактов карточки, не из календарных догадок.</template><template v-else>Графы причин, повторности и 3214-р ещё не рассчитываются.</template> Разделы 7–8 не заполнены. Выгрузка предварительная.</p>
      <div class="report-totals"><section class="card"><small>Заключений эксперта</small><strong>{{show(cell(1,'J')?.value)}}</strong></section><section class="card"><small>Сообщений СНДЗ</small><strong>{{show(cell(1,'F')?.value)}}</strong></section><section class="card"><small>Исследований закончено</small><strong>{{show(cell(1,'T')?.value)}}</strong></section><section class="card"><small>Госзадание выполнено</small><strong>{{show(cell(6,'E')?.value)}}</strong></section></div>
      <section class="card"><h2>Разделы 1–6</h2><div class="button-row" aria-label="Раздел отчёта"><button v-for="s in sections" :key="s.id" :class="{'button-primary':section===s.id}" @click="section=s.id">{{s.id}}. {{s.name}}</button></div><p class="muted">{{active.name}}. Общий итог считается по работам, а не суммированием родительских строк. Нажмите на число или прочерк, чтобы увидеть участвующие записи; на знак вопроса — как считается графа.</p>
       <aside v-if="selectedRule" data-report-rule class="rule-panel" aria-live="polite"><div class="section-heading"><h3>{{rule?`Графа ${rule.official_column} · раздел ${rule.section}`:`Раздел ${selectedRule.section} · столбец ${selectedRule.column}`}}</h3><button type="button" @click="selectedRule=null">Закрыть пояснение</button></div><template v-if="rule"><p>{{rule.meaning}}</p><dl><dt>Единица</dt><dd>{{rule.unit}}</dd><dt>Отчётный период</dt><dd>{{rule.period}}</dd><dt>Источники</dt><dd><ul><li v-for="s in rule.sources" :key="s">{{s}}</li></ul></dd><dt>Когда значение неизвестно</dt><dd><ul><li v-for="s in rule.unknown" :key="s">{{s}}</li></ul></dd><dt>Ограничения текущего расчёта</dt><dd><ul><li v-for="s in rule.limitations" :key="s">{{s}}</li></ul></dd></dl><small class="muted">Редакция правил: {{result.rules_version||'Не указана'}}</small></template><p v-else>Сервер не вернул правило этой графы. Обновите приложение и повторите расчёт; формулу не подставляем предположением.</p></aside>
       <div class="table-scroll"><table><thead><tr><th>Специальность</th><th v-for="column in active.columns" :key="column[0]">{{column[1]}}<button type="button" class="rule-help" :data-column-rule="`${section}-${column[0]}`" :aria-label="`Как считается: ${column[1]}`" :aria-expanded="selectedRule?.section===section&&selectedRule?.column===column[0]" @click="selectedRule={section,column:column[0]!}"/></th></tr></thead><tbody><tr v-for="r in rows" :key="r.base" :class="{'report-total-row':r.base===108}"><th>{{r.label}}</th><td v-for="column in active.columns" :key="column[0]" :title="trace(cell(section,column[0]!,r.base))"><button v-if="cell(section,column[0]!,r.base)?.rows.length" class="report-number" @click="selectedCell=cell(section,column[0]!,r.base)??null">{{show(cell(section,column[0]!,r.base)?.value)}}</button><span v-else>{{show(cell(section,column[0]!,r.base)?.value)}}</span></td></tr></tbody></table></div></section>
      <section v-if="selectedCell" class="card"><h2>{{selectedCell.sheet}} · {{selectedCell.address}}</h2><p>Участвующие записи для значения {{show(selectedCell.value)}}. Прочерк означает, что часть сведений требует уточнения.</p><ul class="trace-links"><li v-for="id in selectedCell.rows" :key="id"><RouterLink v-if="work(id)" :to="`/expertises/${work(id)!.id}`">{{work(id)!.registration_number}}</RouterLink><span v-else>Строка {{id}}</span></li></ul></section>
      <section class="card"><h2>Что осталось уточнить</h2><p class="muted">Пробелы не блокируют предварительную выгрузку, но она не означает готовность к официальной сдаче.</p><details v-for="g in result.gaps" :key="g.code" class="report-gap"><summary>Разделы {{g.sections.join(', ')}} · {{g.message}} <span v-if="g.rows.length">({{g.rows.length}} регистраций)</span></summary><p class="muted">{{g.fields}}</p><ul v-if="result.source.type==='registry'&&g.rows.length" class="trace-links"><li v-for="id in g.rows" :key="id"><RouterLink v-if="work(id)" :to="`/expertises/${work(id)!.id}`">{{work(id)!.registration_number}}</RouterLink></li></ul><p v-else-if="g.rows.length">Строки первого листа: {{g.rows.join(', ')}}</p></details><RouterLink v-if="result.source.id" :to="`/imports/${result.source.id}`">Открыть снимок и исходные строки</RouterLink></section>
    </div>
  </template>
</template>
<style scoped>
.rule-help{display:block;width:32px;height:32px;min-height:32px;margin:8px auto 0;border-radius:50%;padding:0;font-size:16px}.rule-help::before{content:'?'}.rule-panel{padding:20px;background:#f3f6f0;border:1px solid var(--border);border-radius:12px;margin:18px 0}.rule-panel dt{font-weight:600;margin-top:12px}.rule-panel dd{margin:5px 0;overflow-wrap:anywhere}.rule-panel ul{margin:0;padding-left:20px}.rule-panel li{margin:5px 0}
.report-number{border:0;min-height:0;padding:2px 4px;background:transparent;color:var(--green,#215c3a);text-decoration:underline;text-underline-offset:3px;font:inherit}.trace-links{display:flex;gap:8px 24px;flex-wrap:wrap;padding-left:20px}.trace-links li{min-width:130px}
.report-form{display:grid;grid-template-columns:minmax(240px,2fr) 110px minmax(180px,1fr);gap:18px}.report-form label{display:flex;flex-direction:column;gap:7px}.report-form .coverage-check{grid-column:1/-1;flex-direction:row;align-items:center}.coverage-check input{width:18px;height:18px;flex-shrink:0}.report-summary{display:flex;gap:24px;align-items:center;justify-content:space-between}.report-summary h2{margin:4px 0}.report-summary .button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 18px;border-radius:8px;white-space:nowrap;text-decoration:none}.report-totals{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:20px 0}.report-totals strong{display:block;font-size:30px;margin-top:12px}.report-gap{padding:14px 0;border-bottom:1px solid var(--border,#dde3dc)}.report-gap summary{cursor:pointer;line-height:1.6}.report-total-row{font-weight:700;background:#edf3e9}td{text-align:right}th{white-space:normal;min-width:100px}.card{margin-bottom:20px}@media(max-width:900px){.report-form{grid-template-columns:1fr}.report-totals{grid-template-columns:repeat(2,1fr)}.report-summary{align-items:flex-start;flex-direction:column}}
</style>
