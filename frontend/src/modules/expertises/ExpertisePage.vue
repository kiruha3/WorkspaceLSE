<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { Expertise } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import AssignmentForm from './AssignmentForm.vue'
import ProductionPanel from './ProductionPanel.vue'
import ResultPanel from './ResultPanel.vue'
import ExpertiseLetters from '../letters/ExpertiseLetters.vue'
import ExpertiseIssueStatus from '../issuance/ExpertiseIssueStatus.vue'
import HistoricalFacts from './HistoricalFacts.vue'
import HistoryActivation from './HistoryActivation.vue'
import HistoryReportEditor from './HistoryReportEditor.vue'
import HistoryReportDetails from './HistoryReportDetails.vue'
import CaseDetailsPanel from './CaseDetailsPanel.vue'
import ClassificationPanel from './ClassificationPanel.vue'
import TimingPanel from './TimingPanel.vue'
import { useSessionStore } from '../../stores/session'
const api = useApi(), route = useRoute(), requests = new LatestRequest()
const session = useSessionStore()
const expertise = ref<Expertise | null>(null), loading = ref(false), error = ref<unknown>(null), action = ref<'assign' | 'reassign' | null>(null), success = ref('')
const stateLabels = { in_progress: 'В производстве', suspended: 'Приостановлена', completed: 'Завершена', without_execution: 'Без исполнения' }
const natureLabels = { primary: 'Первичная', repeated: 'Повторная', additional: 'Дополнительная' }
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/expertises(?:\?|$)/.test(route.query.return) ? route.query.return : '/expertises')
function time(value: string | null) { return value ? new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Krasnoyarsk', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : 'Не указано' }
async function load() {
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<Expertise>(`/expertises/${route.params.id}/`, { signal }), value => { expertise.value = value; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
function updated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; action.value = null; success.value = 'Назначения сохранены сервером. Номер работы не изменён.' }
function productionUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; success.value = 'Событие производства сохранено сервером.' }
function resultUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; success.value = 'Сведения о результате сохранены сервером.' }
function historyUpdated(value: Expertise) { requests.cancel(); loading.value = false; expertise.value = value; action.value = null; success.value = 'Историческая работа подтверждена для нового учёта. Назначение выполняется отдельно.' }
function historyReportUpdated(value: Expertise) { requests.cancel();loading.value=false;expertise.value=value;success.value='Уточнение сохранено. Номер и состояние работы не изменены.' }
watch(() => route.params.id, () => { if (route.path.startsWith('/expertises/')) { action.value = null; expertise.value = null; success.value = ''; void load() } }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <p v-if="expertise?.material.is_demo" class="message">Учебный материал. Эта работа не включается в отчёт 15.1 по рабочей базе.</p>
  <div class="page-heading"><div><p class="eyebrow">Рабочая карточка экспертизы</p><h1>{{ expertise?.registration_number || 'Экспертиза' }}</h1><p class="muted">{{ expertise?.material.title || 'Серверные данные работы' }}</p></div><RouterLink data-back-to-expertises :to="returnTo">← К реестру экспертиз</RouterLink></div><ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка рабочей карточки…</p>
  <template v-if="expertise">
    <p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <section class="card">
      <div class="section-heading"><div><h2>{{ expertise.registration_number }}</h2><p v-if="expertise.historical_number" class="muted compact">Исторический номер: {{ expertise.historical_number }}</p></div><div class="button-row"><span class="badge" :class="expertise.state === 'in_progress' ? 'badge-green' : ''">{{ stateLabels[expertise.state] }}</span><button :disabled="loading" @click="load">Обновить серверные сведения</button></div></div>
      <dl class="work-facts">
        <div><dt>{{ expertise.origin_kind === 'historical' ? 'Фактический отдел в журнале' : 'Отдел регистрации' }}</dt><dd>{{ expertise.department.code }} · {{ expertise.department.name }}</dd></div>
        <div><dt>Специальность</dt><dd>{{ expertise.specialty ? `${expertise.specialty.code} · ${expertise.specialty.name}` : 'Специальность не уточнена' }}</dd></div>
        <div><dt>Характер назначения</dt><dd>{{ expertise.appointment_nature ? natureLabels[expertise.appointment_nature] : 'Характер назначения не уточнён' }}</dd></div>
        <div><dt>Состав</dt><dd>{{ expertise.is_commission === null ? 'Состав не уточнён' : expertise.is_commission ? 'Комиссионная · один номер' : 'Единоличная' }}</dd></div>
        <div><dt>Поступление</dt><dd>{{ expertise.receipt.received_at }}</dd></div>
        <div><dt>Категория / год</dt><dd>{{ expertise.category_code }} / {{ expertise.year }}</dd></div>
        <div><dt>Комплексная группа</dt><dd>{{ expertise.complex_group?.title || (expertise.complex_group ? expertise.complex_group.id : expertise.historical && !expertise.historical.complex_known ? 'Не уточнена' : 'Не включена') }}</dd></div>
      </dl>
      <p v-if="expertise.complex_group" class="muted compact">В комплексной группе отдельный номер для каждой специальности. Доступ к этой работе не предоставляет доступ ко всем работам материала.</p>
      <p class="muted compact">Версия работы {{ expertise.version }}</p>
      <RouterLink v-if="session.workDocumentsEnabled&&session.can('documents.view')" data-work-document-archive :to="{path:`/expertises/${expertise.id}/documents`,query:{return:route.fullPath}}">Открыть единый архив документов →</RouterLink>
    </section>
    <section class="card stack-card"><div class="section-heading"><div><h2>Текущие исполнители</h2><p class="muted compact">{{ expertise.is_commission ? 'Комиссия выполняет одну работу под одним номером.' : 'Назначение по специальности этой работы.' }}</p></div><div class="button-row"><button v-if="expertise.allowed_actions.includes('expertise.assign') && !action" data-start-assignment class="button-primary" @click="action = 'assign'">Назначить эксперта{{ expertise.is_commission ? 'ов' : '' }}</button><button v-if="expertise.allowed_actions.includes('expertise.reassign') && !action" data-start-assignment @click="action = 'reassign'">Перепоручить</button></div></div><div data-current-assignments><div v-for="assignment in expertise.current_assignments" :key="assignment.id" class="assignment-line"><strong>{{ assignment.employee.full_name }}</strong><small>Назначен: {{ time(assignment.started_at) }}</small><p class="muted compact">{{ assignment.reason || 'Основание не указано' }}</p></div><p v-if="!expertise.current_assignments.length" class="muted">Исполнитель ещё не назначен. Это отдельный признак, состояние работы — {{ stateLabels[expertise.state].toLowerCase() }}.</p></div><AssignmentForm v-if="action" :key="`${expertise.id}-${action}`" :expertise="expertise" :action="action" @updated="updated" @cancel="action = null" /></section>
    <section data-assignment-history class="card stack-card"><h2>История назначений</h2><div v-for="assignment in expertise.assignment_history" :key="assignment.id" class="assignment-line"><strong>{{ assignment.employee.full_name }}</strong><small>{{ time(assignment.started_at) }} → {{ assignment.ended_at ? time(assignment.ended_at) : 'действует' }}</small><p class="muted compact">{{ assignment.reason || 'Основание не указано' }}</p></div><p v-if="!expertise.assignment_history.length" class="muted compact">Предыдущих назначений нет.</p></section><section class="card stack-card"><BasisPreview :document="expertise.basis_document" /></section>
    <HistoricalFacts v-if="expertise.historical" :key="`history-${expertise.id}`" :history="expertise.historical" />
    <CaseDetailsPanel v-if="expertise.case_details" :key="`case-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <ClassificationPanel v-if="expertise.classification" :key="`classification-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <section v-if="expertise.historical?.operational" class="card stack-card"><h2>Исторические отчётные сведения и уточнения</h2><p class="muted compact">Сохраняются после перехода к новому учёту. В отчёте принятый итог нового учёта имеет приоритет.</p><HistoryReportDetails :history="expertise.historical"/></section>
    <HistoryReportEditor v-if="expertise.historical&&!expertise.historical.operational&&['completed','without_execution'].includes(expertise.state)" :key="`report-history-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <HistoryActivation v-if="expertise.historical && !expertise.historical.operational" :key="`activation-${expertise.id}`" :expertise="expertise" @updated="historyUpdated" />
    <ProductionPanel :key="expertise.id" :expertise="expertise" @updated="productionUpdated" />
    <TimingPanel v-if="expertise.timing" :key="`timing-${expertise.id}`" :expertise="expertise" @updated="historyReportUpdated"/>
    <ResultPanel v-if="expertise.result_readiness" :key="expertise.id" :expertise="expertise" @updated="resultUpdated" />
    <ExpertiseLetters v-if="session.correspondenceEnabled && session.can('letters.view')" :key="`letters-${expertise.id}`" :expertise-id="expertise.id" />
    <ExpertiseIssueStatus v-if="session.issuanceEnabled" :key="`issue-${expertise.id}`" :expertise-id="expertise.id" :material-id="expertise.material.id" />
  </template>
</template>
