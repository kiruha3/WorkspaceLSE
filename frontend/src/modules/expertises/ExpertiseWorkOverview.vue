<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import type { Expertise } from '../../api/types'
import BasisPreview from '../../shared/BasisPreview.vue'
import HelpTip from '../../shared/ui/HelpTip.vue'

const props = defineProps<{ expertise: Expertise; archiveTo: RouteLocationRaw; showArchive: boolean; showIssuance: boolean }>()
type Section = 'assignments' | 'production' | 'result' | 'issuance' | 'history'
const emit = defineEmits<{ navigate: [section: Section] }>()
const kinds = { expert_conclusion: 'Заключение эксперта', research_act: 'Акт экспертного исследования', sndz: 'Сообщение о невозможности дать заключение' }
const legacy = computed(() => props.expertise.historical && !props.expertise.historical.operational)
const closed = computed(() => ['completed', 'without_execution'].includes(props.expertise.state))
const accepted = computed(() => props.expertise.closure?.kind === 'completed' && props.expertise.closure.result_id === props.expertise.result?.id)
const resultLabel = computed(() => {
  const work = props.expertise
  if (legacy.value) return work.historical?.result_kind ? `По журналу · ${kinds[work.historical.result_kind]}` : 'В журнале не уточнён'
  if (work.state === 'without_execution') return 'Решение без исполнения'
  if (!work.result) return 'Не добавлен'
  return `${accepted.value ? '' : 'Черновик · '}${work.result.kind ? kinds[work.result.kind] : 'Вид не уточнён'}`
})
const resultDocument = computed(() => {
  const work = props.expertise
  if (legacy.value) return null
  return work.state === 'without_execution' ? work.closure?.document ?? null : work.result?.document ?? work.closure?.document ?? null
})
const next = computed<{ section: Section; label: string }>(() => {
  if (legacy.value) return { section: 'assignments', label: 'Подтверждение нового учёта' }
  if (props.expertise.state === 'suspended') return { section: 'production', label: 'Возобновление и сроки' }
  if (closed.value && props.showIssuance) return { section: 'issuance', label: 'Выдача материалов' }
  return { section: 'result', label: 'Результат и завершение' }
})
function date(value: string | null) { return value ? value.split('-').reverse().join('.') : 'Не указан' }
</script>

<template>
  <div class="work-overview-grid" data-work-overview>
    <section class="work-sheet" aria-labelledby="work-overview-heading">
      <div class="work-sheet-heading"><h2 id="work-overview-heading">Работа по экспертизе</h2><HelpTip label="Действия по экспертизе">Кнопки открывают существующий раздел карточки. Назначение, сохранение результата, завершение и выдача выполняются отдельно с подтверждением в своей форме.</HelpTip></div>
      <div class="work-overview-row">
        <span class="work-row-label">Исполнители в АИС</span>
        <div class="work-row-value"><template v-if="expertise.current_assignments.length"><span v-for="item in expertise.current_assignments" :key="item.id">{{ item.employee.full_name }}</span></template><span v-else>{{ legacy ? 'Назначений в новом учёте нет' : 'Не назначены' }}</span></div>
        <button type="button" data-card-jump="assignments" @click="emit('navigate','assignments')">Открыть исполнителей</button>
      </div>
      <div class="work-overview-row">
        <span class="work-row-label">Срок</span><div class="work-row-value">{{ date(expertise.production.current_due_on) }}<small v-if="expertise.state==='suspended'" class="work-pause">Работа приостановлена</small></div>
        <button type="button" data-card-jump="production" @click="emit('navigate','production')">Открыть сроки</button>
      </div>
      <div class="work-overview-row">
        <span class="work-row-label">Результат</span><div class="work-row-value">{{ resultLabel }}<small v-if="expertise.closure && !legacy">{{ expertise.closure.kind==='completed' ? 'Окончание подтверждено' : 'Решение принято' }} · {{ date(expertise.closure.ended_on) }}</small></div>
        <button type="button" data-card-jump="result" @click="emit('navigate','result')">Открыть результат</button>
      </div>
      <div class="work-overview-next"><span v-if="expertise.is_commission" class="badge badge-green">Комиссионная</span><span v-if="expertise.complex_group" class="badge">Комплексная</span><HelpTip v-if="legacy" label="Исторический учёт">Исполнители и даты исходного журнала показаны отдельно в сводке и истории. Подтверждение нового учёта не означает назначение эксперта.</HelpTip><button type="button" class="button-primary" :data-card-jump="next.section" @click="emit('navigate',next.section)">{{ next.label }} →</button></div>
    </section>
    <section class="work-sheet work-documents" data-card-documents aria-labelledby="work-documents-heading">
      <div class="work-sheet-heading"><h2 id="work-documents-heading">Документы</h2><HelpTip label="Документы экспертизы">Здесь основание и документ результата. Все файлы, их версии, загрузка и связи доступны в архиве. Ограничения доступа сохраняются.</HelpTip></div>
      <BasisPreview :document="expertise.basis_document" heading="Постановление / определение"/>
      <BasisPreview :document="resultDocument" :heading="expertise.state==='without_execution' ? 'Решение без исполнения' : accepted ? 'Документ результата' : 'Документ результата / черновик'" :empty-text="legacy ? 'Документ журнала ещё не подтверждён в новом учёте.' : 'Документ пока не указан.'"/>
      <RouterLink v-if="showArchive" class="work-archive" data-card-archive-link :to="archiveTo">Архив и добавление документов →</RouterLink>
    </section>
  </div>
</template>

<style scoped>
.work-overview-grid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(270px,1fr);gap:14px;align-items:start}
.work-sheet{border:1px solid var(--border);border-radius:6px;background:white;padding:14px;min-width:0}
.work-sheet-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}.work-sheet-heading h2{font-size:16px;margin:0}
.work-overview-row{display:grid;grid-template-columns:minmax(85px,.7fr) minmax(0,1.3fr) auto;gap:10px;align-items:center;border-top:1px solid #edf0e8;padding:10px 0;font-size:13px;min-height:48px}
.work-row-label{color:#65735f}.work-row-value{min-width:0;overflow-wrap:anywhere;font-weight:500}.work-row-value>span{display:block}.work-row-value small{display:block;font-size:11px;color:#6f7d68;margin-top:3px}.work-row-value .work-pause{color:#8c6825}
.work-overview-row button{font-size:12px;min-height:32px;padding:6px 9px;white-space:normal}.work-overview-next{display:flex;gap:7px;align-items:center;flex-wrap:wrap;border-top:1px solid #edf0e8;padding-top:11px;margin-top:3px}.work-overview-next>.button-primary{margin-left:auto;font-size:12px;min-height:33px;padding:7px 10px}
.work-documents>:deep(.document-preview){padding:9px 0;border-top:1px solid #edf0e8}.work-documents>:deep(.document-preview h3){font-size:12px;margin-bottom:5px}.work-archive{display:block;margin-top:10px;font-size:12px}
@media(max-width:1150px){.work-overview-grid{grid-template-columns:minmax(0,1.4fr) minmax(240px,1fr)}.work-overview-row{grid-template-columns:90px minmax(0,1fr)}.work-overview-row>button{grid-column:2;justify-self:start}}
@media(max-width:950px){.work-overview-grid{grid-template-columns:1fr}.work-overview-row{grid-template-columns:105px minmax(0,1fr) auto}.work-overview-row>button{grid-column:auto}}
@media(max-width:600px){.work-sheet{padding:12px}.work-overview-row{grid-template-columns:95px minmax(0,1fr);gap:6px}.work-overview-row>button{grid-column:2;justify-self:start}.work-overview-next>.button-primary{margin-left:0}}
@media(pointer:coarse){.work-overview-row button,.work-overview-next>.button-primary{min-height:38px}}
</style>
