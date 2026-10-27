<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { BasisDocument, DocumentKind, DocumentLink, Expertise, ExpertiseCommandResponse, Reference, ResultKind, ResultOptions, ResultPayload } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'

const props = defineProps<{ expertise: Expertise }>()
const emit = defineEmits<{ updated: [expertise: Expertise] }>()
type Action = 'draft' | 'complete' | 'return' | 'correct'
type Allocation = { reason_id: string; count: string; comment: string; document_id: string }
const api = useApi(), session = useSessionStore(), requests = new LatestRequest()
const action = ref<Action | null>(null), reason = ref(''), saving = ref(false), error = ref<unknown>(null), optionsError = ref<unknown>(null)
const options = ref<ResultOptions | null>(null), loadingOptions = ref(false), uncertain = ref(false)
const attempt = ref<{ key: string; body: Record<string, unknown>; endpoint: string } | null>(null)
const kind = ref<ResultKind | ''>(''), completedOn = ref(''), documentId = ref(''), complexity = ref('')
const questions = ref(''), categorical = ref(''), probable = ref(''), unresolved = ref(''), statisticsComplete = ref(false)
const sndzReason = ref(''), sndzComment = ref(''), allocations = ref<Allocation[]>([]), allocationsComplete = ref(false), note = ref('')
const decidedOn = ref(''), returnReason = ref(''), comment = ref(''), initialDraft = ref('')
const documentForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const labels: Record<ResultKind, string> = { expert_conclusion: 'Заключение эксперта', research_act: 'Акт исследования', sndz: 'СНДЗ' }
const numberFields = [{ key: 'questions', label: 'Q — поставленные вопросы', value: questions }, { key: 'categorical', label: 'R — категорические ответы', value: categorical }, { key: 'probable', label: 'S — вероятные ответы', value: probable }, { key: 'unresolved', label: 'T — нерешённые вопросы', value: unresolved }]
const isReturn = computed(() => action.value === 'return' || (action.value === 'correct' && props.expertise.closure?.kind === 'without_execution'))
const editingResult = computed(() => action.value === 'draft' || (action.value === 'correct' && !isReturn.value))
const closed = computed(() => ['completed', 'without_execution'].includes(props.expertise.state))
const actionCodes = { draft: 'expertise.result.draft', complete: 'expertise.complete', return: 'expertise.return_without_execution', correct: 'expertise.closed.correct' }
const authorized = computed(() => Boolean(action.value && props.expertise.allowed_actions.includes(actionCodes[action.value])))
const recovering = computed(() => uncertain.value && Boolean(attempt.value))
const current = computed(() => props.expertise.result)
const history = computed(() => props.expertise.result_history ?? [])
const closures = computed(() => props.expertise.closure_history ?? [])
const readiness = computed(() => props.expertise.result_readiness ?? { completion_blockers: [], report_gaps: [] })
const receivedOn = computed(() => props.expertise.receipt.received_at.slice(0, 10))
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Krasnoyarsk', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const minimumDate = computed(() => [...props.expertise.suspensions.flatMap(item => [item.suspended_on, item.resumed_on ?? '']), ...props.expertise.deadline_events.map(item => item.recorded_on), receivedOn.value].sort().at(-1)!)
const evidenceKind = computed<DocumentKind | null>(() => isReturn.value ? 'return_decision' : kind.value || null)
const documentKindOptions = computed(() => evidenceKind.value ? [{ value: evidenceKind.value, label: isReturn.value ? 'Решение без исполнения' : labels[kind.value as ResultKind] }] : [])
const allDocuments = computed(() => {
  const links: DocumentLink[] = [props.expertise.basis_document, current.value?.document ?? null, ...history.value.flatMap(item => [item.document, ...item.unresolved_allocations.map(row => row.document)]), ...closures.value.map(item => item.document), ...props.expertise.deadline_events.map(item => item.document)]
  const seen = new Set<string>()
  return links.filter((item): item is BasisDocument => Boolean(item && !('restricted' in item))).filter(item => { if (seen.has(item.id)) return false; seen.add(item.id); return true })
})
const documents = computed(() => allDocuments.value.filter(item => item.kind === evidenceKind.value))
const selectedDocument = computed(() => documents.value.find(item => item.id === documentId.value))
const availableKinds = computed(() => (options.value?.result_kinds ?? []).filter(item => props.expertise.category_code === '6' ? item.code === 'research_act' : item.code !== 'research_act'))
function catalog(values: Reference[] | undefined, retained: (Reference | null | undefined)[]) {
  const items = new Map((values ?? []).filter(item => item.is_active).map(item => [item.id, item]))
  for (const item of retained) if (item && !items.has(item.id)) items.set(item.id, item)
  return [...items.values()]
}
const sndzReasons = computed(() => catalog(options.value?.sndz_reasons, history.value.map(item => item.sndz_reason)))
const unresolvedReasons = computed(() => catalog(options.value?.unresolved_reasons, history.value.flatMap(item => item.unresolved_allocations.map(row => row.reason))))
const returnReasons = computed(() => catalog(options.value?.return_reasons, closures.value.map(item => item.return_reason)))
const numeric = (value: string) => value === '' ? null : Number(value)
const resultPayload = computed<ResultPayload>(() => ({ kind: kind.value || null, completed_on: completedOn.value || null, document_id: documentId.value && documentId.value !== 'new' ? documentId.value : null, complexity_level: numeric(complexity.value), questions: numeric(questions.value), categorical: numeric(categorical.value), probable: numeric(probable.value), unresolved: numeric(unresolved.value), statistics_complete: statisticsComplete.value, sndz_reason_id: kind.value === 'sndz' ? sndzReason.value || null : null, sndz_comment: kind.value === 'sndz' ? sndzComment.value.trim() : '', unresolved_allocations: allocations.value.map(row => ({ reason_id: row.reason_id, count: Number(row.count), comment: row.comment.trim(), document_id: row.document_id || null })), allocations_complete: allocationsComplete.value, note: note.value.trim() }))
const normalizedDraft = computed(() => JSON.stringify([reason.value.trim(), resultPayload.value, documentId.value, decidedOn.value, returnReason.value, comment.value.trim()]))
const dirty = computed(() => Boolean(action.value && (normalizedDraft.value !== initialDraft.value || documentForm.value?.dirty || attempt.value)))
const confirmLeave = useDirtyGuard(() => dirty.value || saving.value, inject(routerKey, undefined))
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && attempt.value && attempt.value.body.expected_version !== props.expertise.version)
const validation = computed(() => {
  if (!action.value || recovering.value) return ''
  if (!authorized.value) return 'Действие больше не разрешено. Введённые данные сохранены.'
  if (!reason.value.trim()) return 'Укажите причину / основание.'
  if (action.value === 'complete') return !current.value || readiness.value.completion_blockers.length ? 'Устраните препятствия завершению.' : ''
  if (loadingOptions.value || !options.value) return 'Загрузите справочники результата.'
  if (isReturn.value) {
    if (!decidedOn.value || decidedOn.value < minimumDate.value || decidedOn.value > today()) return 'Укажите допустимую дату решения.'
    if (!documentId.value || (documentId.value !== 'new' && !selectedDocument.value?.versions.length)) return 'Для решения нужен сохранённый файл документа.'
    return ''
  }
  const p = resultPayload.value, numbers = [p.questions, p.categorical, p.probable, p.unresolved]
  if (action.value === 'correct' && (!p.kind || !p.completed_on || !documentId.value || (documentId.value !== 'new' && !selectedDocument.value?.versions.length))) return 'Исправление завершённой работы требует вида результата, даты и сохранённого файла.'
  if (numbers.some(value => value !== null && (!Number.isInteger(value) || value < 0)) || (p.complexity_level !== null && (!Number.isInteger(p.complexity_level) || p.complexity_level < 1))) return 'Количество — целое неотрицательное число; сложность — целое от 1.'
  const sum = (p.categorical ?? 0) + (p.probable ?? 0) + (p.unresolved ?? 0), allKnown = numbers.every(value => value !== null)
  if (p.questions !== null && (sum > p.questions || (allKnown && sum !== p.questions))) return 'Известные ответы должны соответствовать числу вопросов Q.'
  if (p.statistics_complete && !allKnown) return 'Для подтверждения статистики заполните Q, R, S и T.'
  if (p.completed_on && (p.completed_on < minimumDate.value || p.completed_on > today())) return 'Дата окончания должна соответствовать фактам производства.'
  if (p.kind && !availableKinds.value.some(item => item.code === p.kind)) return 'Выберите вид результата для категории работы.'
  if (documentId.value && documentId.value !== 'new' && !selectedDocument.value) return 'Выберите документ соответствующего вида.'
  const ids = p.unresolved_allocations.map(row => row.reason_id)
  if (new Set(ids).size !== ids.length) return 'Причины нерешённых вопросов не должны повторяться.'
  if (p.unresolved_allocations.some(row => !unresolvedReasons.value.some(item => item.id === row.reason_id) || !Number.isInteger(row.count) || row.count < 1 || (unresolvedReasons.value.find(item => item.id === row.reason_id)?.code === 'other' && !row.comment))) return 'Для каждой причины нужны количество и пояснение для «Другое».'
  const allocated = p.unresolved_allocations.reduce((sum, row) => sum + row.count, 0)
  if (p.unresolved !== null && allocated > p.unresolved) return 'Распределение превышает T.'
  if (p.allocations_complete && (p.unresolved === null || allocated !== p.unresolved)) return 'Подтверждённое распределение должно равняться T.'
  return ''
})
const valid = computed(() => Boolean(action.value && (authorized.value || recovering.value) && !validation.value))
function invalidateAttempt() { attempt.value = null; uncertain.value = false }
watch(normalizedDraft, invalidateAttempt, { flush: 'sync' })
watch(kind, () => { documentId.value = '' }, { flush: 'sync' })
async function loadOptions() {
  loadingOptions.value = true; optionsError.value = null
  try { await requests.run(signal => api.request<ResultOptions>(`/expertises/${props.expertise.id}/result-options/`, { signal }), value => { options.value = value; loadingOptions.value = false }) }
  catch (cause) { optionsError.value = cause; loadingOptions.value = false }
}
function start(value: Action) {
  if (!props.expertise.allowed_actions.includes(actionCodes[value])) return
  action.value = value; error.value = null; reason.value = ''; invalidateAttempt()
  const r = current.value
  kind.value = r?.kind ?? ''; completedOn.value = r?.completed_on ?? ''; documentId.value = (isReturn.value ? props.expertise.closure?.document : r?.document)?.id ?? ''
  complexity.value = String(r?.complexity_level ?? ''); questions.value = String(r?.questions ?? ''); categorical.value = String(r?.categorical ?? ''); probable.value = String(r?.probable ?? ''); unresolved.value = String(r?.unresolved ?? '')
  statisticsComplete.value = r?.statistics_complete ?? false; sndzReason.value = r?.sndz_reason?.id ?? ''; sndzComment.value = r?.sndz_comment ?? ''; allocationsComplete.value = r?.allocations_complete ?? false; note.value = r?.note ?? ''
  allocations.value = (r?.unresolved_allocations ?? []).map(row => ({ reason_id: row.reason.id, count: String(row.count), comment: row.comment, document_id: row.document?.id ?? '' }))
  decidedOn.value = isReturn.value && value === 'correct' ? props.expertise.closure?.ended_on ?? '' : today(); returnReason.value = value === 'correct' ? props.expertise.closure?.return_reason?.id ?? '' : ''; comment.value = value === 'correct' ? props.expertise.closure?.comment ?? '' : ''
  initialDraft.value = normalizedDraft.value
  if (value !== 'complete') void loadOptions()
}
function cancel() { if (!saving.value && confirmLeave()) { action.value = null; error.value = null; invalidateAttempt(); requests.cancel() } }
function acceptVersion() { invalidateAttempt(); error.value = null }
async function save() {
  if (!valid.value || saving.value || !action.value) return
  saving.value = true; error.value = null
  try {
    if (!attempt.value) {
      let evidence = documentId.value && documentId.value !== 'new' ? documentId.value : null
      if (documentId.value === 'new' && action.value !== 'complete') {
        if (!documentForm.value) return
        const document = await documentForm.value.persist()
        if ((isReturn.value || action.value === 'correct') && !document.versions.length) throw new ApiError(400, 'file_required', 'Сохраните файл документа перед подтверждением окончания.')
        evidence = document.id
      }
      const body: Record<string, unknown> = { expected_version: props.expertise.version, reason: reason.value.trim() }
      let endpoint = 'result'
      if (action.value === 'complete') { endpoint = 'complete'; body.result_id = current.value!.id }
      else if (isReturn.value) { endpoint = action.value === 'correct' ? 'correct' : 'return-without-execution'; Object.assign(body, { decided_on: decidedOn.value, document_id: evidence, return_reason_id: returnReason.value || null, comment: comment.value.trim() }); if (action.value === 'correct') body.correction_kind = 'return' }
      else if (action.value === 'correct') { endpoint = 'correct'; body.correction_kind = 'result'; body.result = { ...resultPayload.value, document_id: evidence } }
      else Object.assign(body, { ...resultPayload.value, document_id: evidence })
      attempt.value = { key: newCommandKey(), body, endpoint }
    }
    const response = await api.request<ExpertiseCommandResponse>(`/expertises/${props.expertise.id}/${attempt.value.endpoint}/`, { method: 'POST', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
    action.value = null; invalidateAttempt(); emit('updated', response.expertise)
  } catch (cause) { error.value = cause; uncertain.value = Boolean(attempt.value) && (!(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response') }
  finally { saving.value = false }
}
function time(value: string) { return new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Krasnoyarsk', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) }
onBeforeUnmount(() => requests.cancel())
</script>

<template>
  <section data-result-panel class="card stack-card">
    <div class="section-heading"><div><h2>Результат и завершение</h2><p class="muted compact">Черновик результата, подтверждение окончания и решение без исполнения сохраняются отдельными событиями.</p></div><div v-if="!action" class="button-row"><button v-if="!closed && expertise.allowed_actions.includes('expertise.result.draft')" data-result-draft @click="start('draft')">Внести результат / черновик</button><button v-if="!closed && expertise.allowed_actions.includes('expertise.complete')" data-result-complete class="button-primary" :disabled="!current || readiness.completion_blockers.length > 0" @click="start('complete')">Завершить работу</button><button v-if="!closed && expertise.allowed_actions.includes('expertise.return_without_execution')" data-result-return @click="start('return')">Решение без исполнения</button><button v-if="closed && expertise.closure && expertise.allowed_actions.includes('expertise.closed.correct')" data-result-correct @click="start('correct')">Исправить закрытую работу</button></div></div>
    <section data-completion-blockers class="subsection"><h3>Готовность к завершению</h3><p v-for="issue in readiness.completion_blockers" :key="`${issue.code}-${issue.field}`" class="message message-error">{{ issue.message }}</p><p v-if="!readiness.completion_blockers.length" class="muted compact">{{ expertise.closure ? 'Окончание подтверждено.' : 'Сервер не сообщил препятствий завершению.' }}</p></section>
    <section data-report-gaps class="subsection"><h3>Пробелы отчётных сведений</h3><p class="muted compact">Неизвестные сведения остаются неизвестными. Пробелы отчёта сами по себе не блокируют завершение.</p><p v-for="issue in readiness.report_gaps" :key="`${issue.code}-${issue.field}`" class="compact">{{ issue.message }}</p><p v-if="!readiness.report_gaps.length" class="muted compact">Пробелы не отмечены сервером.</p></section>
    <section v-if="current" data-current-result class="subsection"><h3>Текущая редакция №{{ current.number }} · {{ current.kind ? labels[current.kind] : 'Вид неизвестен' }}</h3><dl class="work-facts"><div><dt>Дата окончания</dt><dd>{{ current.completed_on || 'Неизвестно' }}</dd></div><div><dt>Сложность</dt><dd>{{ current.complexity_level ?? 'Неизвестно' }}{{ current.complexity_level && current.complexity_level > 3 ? ' · группа выше 3' : '' }}</dd></div><div><dt>Q / R / S / T</dt><dd>{{ current.questions ?? 'Неизвестно' }} / {{ current.categorical ?? 'Неизвестно' }} / {{ current.probable ?? 'Неизвестно' }} / {{ current.unresolved ?? 'Неизвестно' }}</dd></div></dl><p class="compact">Статистика {{ current.statistics_complete ? 'подтверждена' : 'не подтверждена' }} · распределение T {{ current.allocations_complete ? 'подтверждено' : 'не подтверждено' }}</p><p v-if="current.kind === 'sndz'" class="compact">Причина полного СНДЗ: {{ current.sndz_reason?.name || 'Неизвестно' }}. {{ current.sndz_comment }}</p><p v-for="row in current.unresolved_allocations" :key="row.reason.id" class="compact">Нерешённые: {{ row.reason.name }} — {{ row.count }}. {{ row.comment }}</p><p class="compact">{{ current.note }}</p><BasisPreview :document="current.document" heading="Документ результата" empty-text="Документ результата не указан." /></section>
    <p v-else class="muted compact">Результат пока не сохранён.</p>
    <section v-if="expertise.closure" data-current-closure class="subsection"><h3>{{ expertise.closure.kind === 'completed' ? 'Завершение подтверждено' : 'Решение без исполнения' }} · {{ expertise.closure.ended_on }}</h3><p class="compact">{{ expertise.closure.return_reason?.name || (expertise.closure.kind === 'without_execution' ? 'Причина возврата неизвестна' : '') }} {{ expertise.closure.comment }}</p><p class="muted compact">Выдача или фактический возврат этим решением не оформляются.</p><BasisPreview v-if="expertise.closure.kind === 'without_execution'" :document="expertise.closure.document" heading="Документ решения" empty-text="Документ решения не указан." /></section>
    <form v-if="action" data-result-form class="inset-form form-grid" @submit.prevent="save">
      <h3>{{ action === 'complete' ? 'Подтвердить завершение' : action === 'correct' ? 'Исправление закрытой работы' : isReturn ? 'Решение без исполнения' : 'Редакция результата' }}</h3>
      <ApiMessage :error="error" /><ApiMessage :error="optionsError" />
      <p v-if="loadingOptions" class="muted compact">Загрузка справочников…</p><button v-if="optionsError" type="button" @click="loadOptions">Повторить загрузку справочников</button>
      <p v-if="recovering" class="message">Ответ на команду не получен. Повтор сохранит исходные данные, версию и ключ.</p><p v-else-if="!authorized" class="message message-error">Действие больше не разрешено. Введённые данные сохранены.</p>
      <p v-if="conflict" class="message message-error">Карточка обновлена; черновик сохранён. <button data-result-accept-version type="button" :disabled="saving || !authorized" @click="acceptVersion">Применить версию {{ expertise.version }} к новой попытке</button></p>
      <fieldset class="form-grid" :disabled="saving || (!authorized && !recovering)">
        <template v-if="editingResult">
          <div class="form-columns"><label>Вид результата<select v-model="kind" name="result_kind"><option value="">Неизвестен / ещё не определён</option><option v-for="item in availableKinds" :key="item.code" :value="item.code">{{ item.name }}</option></select></label><label>Дата окончания, если известна<input v-model="completedOn" name="completed_on" type="date" :min="minimumDate" :max="today()" /></label><label>Уровень сложности, если известен<input v-model="complexity" name="complexity_level" type="number" min="1" step="1" /><small>Точное число выше 3 сохраняется без округления.</small></label></div>
          <p class="muted compact">Пустое числовое поле означает неизвестное; 0 — известное отсутствие. Полный СНДЗ не создаёт распределение нерешённых вопросов.</p>
          <div class="form-columns"><label v-for="field in numberFields" :key="field.key">{{ field.label }}<input v-model="field.value.value" :name="field.key" type="number" min="0" step="1" /></label></div>
          <label class="check-label"><input v-model="statisticsComplete" name="statistics_complete" type="checkbox" />Полнота статистики Q = R + S + T подтверждена</label>
          <template v-if="kind === 'sndz'"><label>Одна однозначная причина полного СНДЗ<select v-model="sndzReason" name="sndz_reason_id"><option value="">Неизвестна / не определена</option><option v-for="item in sndzReasons" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_active ? '' : ' (неактивна, сохранена ранее)' }}</option></select></label><label>Пояснение к полному СНДЗ<textarea v-model="sndzComment" name="sndz_comment" rows="2" /></label><p class="muted compact">Несколько причин не сводите к произвольной основной: оставьте причину неизвестной и опишите ситуацию.</p></template>
          <section class="subsection"><h4>Распределение нерешённых вопросов T</h4><div v-for="(row, index) in allocations" :key="index" class="inset-form form-grid"><div class="form-columns"><label>Причина<select v-model="row.reason_id" :name="`allocation_reason_${index}`"><option value="">Выберите причину</option><option v-for="item in unresolvedReasons" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_active ? '' : ' (неактивна, сохранена ранее)' }}</option></select></label><label>Количество<input v-model="row.count" :name="`allocation_count_${index}`" type="number" min="1" step="1" /></label></div><label>Пояснение<textarea v-model="row.comment" :name="`allocation_comment_${index}`" rows="2" /></label><label>Подтверждающий документ, если есть<select v-model="row.document_id" :name="`allocation_document_${index}`"><option value="">Не указан</option><option v-for="item in allDocuments" :key="item.id" :value="item.id">{{ item.title || item.id }}</option></select></label><button type="button" class="align-start" @click="allocations.splice(index, 1)">Удалить строку</button></div><button data-add-allocation type="button" @click="allocations.push({ reason_id: '', count: '', comment: '', document_id: '' })">Добавить причину нерешённых вопросов</button><label class="check-label"><input v-model="allocationsComplete" name="allocations_complete" type="checkbox" />Распределение T подтверждено полностью</label></section>
          <label>Примечание к результату<textarea v-model="note" name="result_note" rows="2" /></label>
        </template>
        <template v-if="isReturn"><label>Дата решения<input v-model="decidedOn" name="decided_on" type="date" :min="minimumDate" :max="today()" required /></label><label>Причина решения без исполнения<select v-model="returnReason" name="return_reason_id"><option value="">Неизвестна / не определена</option><option v-for="item in returnReasons" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_active ? '' : ' (неактивна, сохранена ранее)' }}</option></select></label><label>Пояснение к решению<textarea v-model="comment" name="return_comment" rows="2" /></label></template>
        <template v-if="action !== 'complete'"><label>{{ isReturn ? 'Документ решения' : 'Документ результата' }}<select v-model="documentId" name="result_document"><option value="">Не указан</option><option v-if="session.can('documents.upload') && evidenceKind" value="new">Подготовить новый документ</option><option v-for="item in documents" :key="item.id" :value="item.id">{{ item.title || item.id }}{{ item.versions.length ? '' : ' (файл пока не сохранён)' }}</option></select></label><BasisDocumentForm v-if="documentId === 'new'" :key="evidenceKind || 'unknown'" ref="documentForm" :department-id="expertise.department.id" :busy="saving" :kind-options="documentKindOptions" :heading="isReturn ? 'Документ решения' : 'Документ результата'" @changed="invalidateAttempt" /><p class="muted compact">Для подтверждения окончания нужен сохранённый файл соответствующего вида. Черновик можно сохранить без файла.</p></template>
        <p v-else class="muted compact">Будет подтверждена текущая сохранённая редакция №{{ current?.number }} с её датой окончания. Пробелы отчёта сохранятся явно.</p>
        <label>Причина / основание<textarea v-model="reason" name="result_reason" required rows="3" /></label>
      </fieldset>
      <p v-if="validation && authorized && !recovering" class="muted compact" role="status">{{ validation }}</p>
      <div class="button-row"><button data-result-submit type="submit" class="button-primary" :formnovalidate="recovering" :disabled="saving || !valid">{{ saving ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : action === 'complete' ? 'Подтвердить завершение' : action === 'correct' ? 'Сохранить исправление' : isReturn ? 'Подтвердить решение' : 'Сохранить редакцию результата' }}</button><button type="button" :disabled="saving" @click="cancel">Отмена</button></div>
    </form>
    <section data-result-history class="subsection"><h3>История редакций результата</h3><details v-for="revision in history" :key="revision.id" class="assignment-line"><summary>№{{ revision.number }} · {{ revision.kind ? labels[revision.kind] : 'Вид неизвестен' }} · {{ revision.completed_on || 'Дата неизвестна' }}</summary><p class="compact">{{ revision.actor.full_name }} · {{ time(revision.created_at) }} · {{ revision.reason }}</p><p class="compact">Q / R / S / T: {{ revision.questions ?? 'Неизвестно' }} / {{ revision.categorical ?? 'Неизвестно' }} / {{ revision.probable ?? 'Неизвестно' }} / {{ revision.unresolved ?? 'Неизвестно' }}. Сложность: {{ revision.complexity_level ?? 'Неизвестно' }}.</p><p class="compact">{{ revision.sndz_reason?.name }} {{ revision.sndz_comment }} {{ revision.note }}</p><div v-for="row in revision.unresolved_allocations" :key="row.reason.id"><p class="compact">{{ row.reason.name }}: {{ row.count }} · {{ row.comment }}</p><BasisPreview v-if="row.document" :document="row.document" heading="Документ причины нерешённых вопросов" /></div><BasisPreview :document="revision.document" heading="Документ редакции" empty-text="Документ не указан." /></details><p v-if="!history.length" class="muted compact">Редакций пока нет.</p></section>
    <section data-closure-history class="subsection"><h3>История подтверждений окончания</h3><details v-for="closure in closures" :key="closure.id" class="assignment-line"><summary>№{{ closure.number }} · {{ closure.kind === 'completed' ? 'Завершение' : 'Без исполнения' }} · {{ closure.ended_on }}</summary><p class="compact">{{ closure.actor.full_name }} · {{ time(closure.created_at) }} · {{ closure.reason }}</p><p class="compact">{{ closure.return_reason?.name }} {{ closure.comment }}{{ closure.result_id ? ` · Редакция: ${closure.result_id}` : '' }}</p><BasisPreview :document="closure.document" heading="Документ подтверждения окончания" empty-text="Документ не указан." /></details><p v-if="!closures.length" class="muted compact">Подтверждённого окончания нет. Неизвестная дата окончания не означает выдачу.</p></section>
  </section>
</template>
