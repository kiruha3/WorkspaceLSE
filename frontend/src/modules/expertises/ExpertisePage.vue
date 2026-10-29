<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { Expertise } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import AssignmentForm from './AssignmentForm.vue'
import ProductionPanel from './ProductionPanel.vue'
import ResultPanel from './ResultPanel.vue'
import ReopenWork from './ReopenWork.vue'
import ExpertiseLetters from '../letters/ExpertiseLetters.vue'
import ExpertiseIssueStatus from '../issuance/ExpertiseIssueStatus.vue'
import HistoricalFacts from './HistoricalFacts.vue'
import HistoryActivation from './HistoryActivation.vue'
import HistoryReportEditor from './HistoryReportEditor.vue'
import HistoryReportDetails from './HistoryReportDetails.vue'
import CaseDetailsPanel from './CaseDetailsPanel.vue'
import ClassificationPanel from './ClassificationPanel.vue'
import TimingPanel from './TimingPanel.vue'
import ExpertiseOverview from './ExpertiseOverview.vue'
import ExpertiseSummary from './ExpertiseSummary.vue'
import { useSessionStore } from '../../stores/session'
const api = useApi(), route = useRoute(), requests = new LatestRequest()
const session = useSessionStore()
const expertise = ref<Expertise | null>(null), loading = ref(false), error = ref<unknown>(null), action = ref<'assign' | 'reassign' | null>(null), success = ref('')
const stateLabels = { in_progress: 'В производстве', suspended: 'Приостановлена', completed: 'Завершена', without_execution: 'Без исполнения' }
type CardTab = 'overview' | 'case' | 'assignments' | 'production' | 'result' | 'letters' | 'issuance' | 'history'
const selectedTab = ref<CardTab>('overview'), tabList = ref<HTMLElement | null>(null)
const tabs = computed<{ id: CardTab; label: string }[]>(() => [
  { id: 'overview', label: 'Обзор' }, { id: 'case', label: 'Дело' }, { id: 'assignments', label: 'Исполнители' },
  { id: 'production', label: 'Производство и сроки' }, { id: 'result', label: 'Результат' },
  ...(session.correspondenceEnabled && session.can('letters.view') ? [{ id: 'letters' as const, label: 'Переписка' }] : []),
  ...(session.issuanceEnabled ? [{ id: 'issuance' as const, label: 'Выдача' }] : []),
  ...(expertise.value?.historical ? [{ id: 'history' as const, label: 'История' }] : []),
])
watch(tabs, value => { if (!value.some(tab => tab.id === selectedTab.value)) selectedTab.value = 'overview' })
async function moveTab(event: KeyboardEvent, index: number) {
  let next: number
  if (event.key === 'ArrowRight') next = (index + 1) % tabs.value.length
  else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.value.length) % tabs.value.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = tabs.value.length - 1
  else return
  event.preventDefault()
  selectedTab.value = tabs.value[next]!.id
  await nextTick()
  tabList.value?.querySelector<HTMLButtonElement>(`[data-card-tab="${selectedTab.value}"]`)?.focus()
}
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/(?:expertises|workspace)(?:\?|$)/.test(route.query.return) ? route.query.return : '/expertises')
function time(value: string | null) { return value ? new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Krasnoyarsk', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : 'Не указано' }
async function load() {
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<Expertise>(`/expertises/${route.params.id}/`, { signal }), value => { expertise.value = value; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
function updated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; action.value = null; success.value = 'Назначения сохранены сервером. Номер работы не изменён.' }
function productionUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; success.value = 'Событие производства сохранено сервером.' }
function resultUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; success.value = 'Сведения о результате сохранены сервером.' }
function reopened(value: Expertise) {
  if (expertise.value && (expertise.value.id !== value.id || expertise.value.version > value.version)) return
  requests.cancel(); loading.value = false; expertise.value = value
  success.value = value.state === 'suspended' ? 'Завершение отменено. Работа приостановлена: прежняя приостановка ещё не закрыта.' : value.state === 'in_progress' ? 'Экспертиза возвращена в работу. История и документы сохранены.' : `Команда возврата уже выполнена ранее. Текущее состояние — «${stateLabels[value.state]}».`
}
function historyUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; action.value = null; success.value = 'Историческая работа подтверждена для нового учёта. Назначение выполняется отдельно.' }
function historyReportUpdated(value: Expertise) { requests.cancel();loading.value=false;expertise.value=value;success.value='Уточнение сохранено. Номер и состояние работы не изменены.' }
watch(() => route.params.id, () => { if (route.path.startsWith('/expertises/')) { selectedTab.value = 'overview'; action.value = null; expertise.value = null; success.value = ''; void load() } }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
 <div class="expertise-card">
  <p v-if="expertise?.material.is_demo" class="message">Учебный материал. Эта работа не включается в отчёт 15.1 по рабочей базе.</p>
  <RouterLink class="card-back" data-back-to-expertises :to="returnTo">{{ returnTo.startsWith('/workspace') ? '← К личному кабинету' : '← К реестру экспертиз' }}</RouterLink>
  <div class="expertise-heading"><div><p class="eyebrow">Рабочая карточка экспертизы</p><div class="expertise-title"><h1>{{ expertise?.registration_number || 'Экспертиза' }}</h1><span v-if="expertise" class="badge badge-green">{{ stateLabels[expertise.state] }}</span></div><p class="muted">{{ expertise?.material.title || 'Серверные данные работы' }}</p><p v-if="expertise?.historical_number" class="muted">Исторический номер: {{ expertise.historical_number }}</p></div><div v-if="expertise" class="expertise-tools"><button :disabled="loading" @click="load">Обновить серверные сведения</button><RouterLink v-if="session.workDocumentsEnabled&&session.can('documents.view')" data-work-document-archive :to="{path:`/expertises/${expertise.id}/documents`,query:{return:route.fullPath}}">Открыть единый архив документов →</RouterLink></div></div>
  <ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка рабочей карточки…</p>
  <template v-if="expertise">
    <p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <ExpertiseSummary :expertise="expertise"/>
    <nav ref="tabList" class="card-tabs" role="tablist" aria-label="Разделы карточки экспертизы"><button v-for="(tab,index) in tabs" :id="`card-tab-${expertise.id}-${tab.id}`" :key="tab.id" type="button" role="tab" :data-card-tab="tab.id" :aria-selected="selectedTab===tab.id" :aria-controls="`card-panel-${expertise.id}-${tab.id}`" :tabindex="selectedTab===tab.id?0:-1" @click="selectedTab=tab.id" @keydown="moveTab($event,index)">{{ tab.label }}</button></nav>
    <div :id="`card-panel-${expertise.id}-overview`" data-card-panel="overview" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-overview`" v-show="selectedTab==='overview'" tabindex="0"><ExpertiseOverview :expertise="expertise"/></div>
    <div :id="`card-panel-${expertise.id}-assignments`" data-card-panel="assignments" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-assignments`" v-show="selectedTab==='assignments'" tabindex="0">
    <HistoryActivation v-if="expertise.historical && !expertise.historical.operational" :key="`activation-${expertise.id}`" :expertise="expertise" @updated="historyUpdated" />
    <section class="card stack-card"><div class="section-heading"><div><h2>Текущие исполнители <HelpTip label="Назначение исполнителей">{{ expertise.is_commission ? 'Комиссия выполняет одну работу под одним номером.' : 'Назначение по специальности этой работы.' }}</HelpTip></h2></div><div class="button-row"><button v-if="expertise.allowed_actions.includes('expertise.assign') && !action" data-start-assignment class="button-primary" @click="action = 'assign'">Назначить эксперта{{ expertise.is_commission ? 'ов' : '' }}</button><button v-if="expertise.allowed_actions.includes('expertise.reassign') && !action" data-start-assignment @click="action = 'reassign'">Перепоручить</button></div></div><div data-current-assignments><div v-for="assignment in expertise.current_assignments" :key="assignment.id" class="assignment-line"><strong>{{ assignment.employee.full_name }}</strong><small>Назначен: {{ time(assignment.started_at) }}</small><p class="muted compact">{{ assignment.reason || 'Основание не указано' }}</p></div><p v-if="!expertise.current_assignments.length" class="muted">Исполнитель ещё не назначен. <HelpTip label="Состояние и назначение">Назначение — отдельный признак; состояние работы — {{ stateLabels[expertise.state].toLowerCase() }}.</HelpTip></p></div><AssignmentForm v-if="action" :key="`${expertise.id}-${action}`" :expertise="expertise" :action="action" @updated="updated" @cancel="action = null" /></section>
    <section data-assignment-history class="card stack-card"><h2>История назначений</h2><div v-for="assignment in expertise.assignment_history" :key="assignment.id" class="assignment-line"><strong>{{ assignment.employee.full_name }}</strong><small>{{ time(assignment.started_at) }} → {{ assignment.ended_at ? time(assignment.ended_at) : 'действует' }}</small><p class="muted compact">{{ assignment.reason || 'Основание не указано' }}</p></div><p v-if="!expertise.assignment_history.length" class="muted compact">Предыдущих назначений нет.</p></section>
    </div>
    <div :id="`card-panel-${expertise.id}-case`" data-card-panel="case" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-case`" v-show="selectedTab==='case'" tabindex="0">
    <section class="card stack-card"><BasisPreview :document="expertise.basis_document" /></section>
    <CaseDetailsPanel v-if="expertise.case_details" :key="`case-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <ClassificationPanel v-if="expertise.classification" :key="`classification-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    </div>
    <div :id="`card-panel-${expertise.id}-result`" data-card-panel="result" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-result`" v-show="selectedTab==='result'" tabindex="0">
    <ReopenWork :key="`reopen-${expertise.id}`" :expertise="expertise" @updated="reopened" @refresh="load" />
    <section v-if="expertise.historical?.operational" class="card stack-card"><h2>Исторические отчётные сведения и уточнения <HelpTip label="Исторические отчётные сведения">Сохраняются после перехода к новому учёту. В отчёте принятый итог нового учёта имеет приоритет.</HelpTip></h2><HistoryReportDetails :history="expertise.historical"/></section>
    <HistoryReportEditor v-if="expertise.historical&&!expertise.historical.operational&&['completed','without_execution'].includes(expertise.state)" :key="`report-history-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <ResultPanel v-if="expertise.result_readiness" :key="expertise.id" :expertise="expertise" @updated="resultUpdated" />
    </div>
    <div :id="`card-panel-${expertise.id}-production`" data-card-panel="production" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-production`" v-show="selectedTab==='production'" tabindex="0">
    <ProductionPanel :key="expertise.id" :expertise="expertise" @updated="productionUpdated" />
    <TimingPanel v-if="expertise.timing" :key="`timing-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    </div>
    <div v-if="session.correspondenceEnabled && session.can('letters.view')" :id="`card-panel-${expertise.id}-letters`" data-card-panel="letters" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-letters`" v-show="selectedTab==='letters'" tabindex="0">
    <ExpertiseLetters v-if="session.correspondenceEnabled && session.can('letters.view')" :key="`letters-${expertise.id}`" :expertise-id="expertise.id" />
    </div>
    <div v-if="session.issuanceEnabled" :id="`card-panel-${expertise.id}-issuance`" data-card-panel="issuance" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-issuance`" v-show="selectedTab==='issuance'" tabindex="0">
    <ExpertiseIssueStatus v-if="session.issuanceEnabled" :key="`issue-${expertise.id}`" :expertise-id="expertise.id" :material-id="expertise.material.id" />
    </div>
    <div v-if="expertise.historical" :id="`card-panel-${expertise.id}-history`" data-card-panel="history" class="card-tab-panel" role="tabpanel" :aria-labelledby="`card-tab-${expertise.id}-history`" v-show="selectedTab==='history'" tabindex="0">
    <HistoricalFacts :key="`history-${expertise.id}`" :history="expertise.historical" />
    </div>
  </template>
 </div>
</template>

<style scoped>
.expertise-card { --muted: #5c6e61; }
.card-back { display: inline-block; margin-bottom: 18px; font-size: 13px; }
.expertise-heading { display: flex; justify-content: space-between; align-items: center; gap: 24px; margin-bottom: 24px; }
.expertise-heading > div { min-width: 0; }
.expertise-title { display: flex; align-items: center; flex-wrap: wrap; gap: 18px; }
.expertise-title h1 { font-size: 36px; margin: 7px 0; overflow-wrap: anywhere; }
.expertise-title .badge { font-size: 13px; padding: 6px 12px; }
.expertise-heading .muted { font-size: 13px; overflow-wrap: anywhere; }
.expertise-tools { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 14px 20px; font-size: 13px; }
.card-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border); overflow-x: auto; margin-bottom: 24px; padding: 3px 3px 0; }
.card-tabs button { flex: 0 0 auto; border: 0; border-bottom: 3px solid transparent; border-radius: 0; padding: 13px 12px; background: transparent; color: #4f6055; font-size: 14px; white-space: nowrap; }
.card-tabs button[aria-selected=true] { color: var(--green); border-bottom-color: var(--green); }
.card-tab-panel > :deep(.card) { margin-top: 0; margin-bottom: 20px; }
.expertise-card :deep(.work-facts dt) { font-size: 13px; }
.expertise-card :deep(.work-facts dd) { font-size: 14px; }
.expertise-card :deep(.compact) { font-size: 13px; }
@media (max-width: 1100px) { .expertise-heading { align-items: flex-start; flex-wrap: wrap; } .expertise-tools { justify-content: flex-start; } }
@media (max-width: 600px) { .expertise-title h1 { font-size: 28px; } .expertise-tools { width: 100%; gap: 12px; } .expertise-tools button { width: 100%; } .card-tabs { margin-bottom: 18px; } }
</style>
