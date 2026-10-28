<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { BasisDocument, DeadlineKind, DocumentKind, Expertise } from '../../api/types'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'

const props = defineProps<{ expertise: Expertise }>()
const emit = defineEmits<{ updated: [expertise: Expertise] }>()
type Action = 'suspend' | 'resume' | 'deadline'
type CommandBody = { expected_version: number; reason: string; suspended_on?: string; resumed_on?: string; kind?: DeadlineKind; recorded_on?: string; due_on?: string; document_id?: string | null }
const api = useApi(), action = ref<Action | null>(null), reason = ref(''), factualOn = ref(''), dueOn = ref(''), kind = ref<DeadlineKind>('initial'), documentId = ref('')
const saving = ref(false), error = ref<unknown>(null), uncertain = ref(false), attempt = ref<{ key: string; body: CommandBody } | null>(null)
const initialDraft = ref('')
const documentForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const labels: Record<DeadlineKind, string> = { initial: 'Исходный срок / уточнение', request: 'Запрос нового срока', agreement: 'Согласование срока' }
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Krasnoyarsk', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const receivedOn = computed(() => props.expertise.receipt.received_at.slice(0, 10))
const closed = computed(() => ['completed', 'without_execution'].includes(props.expertise.state))
const openPause = computed(() => props.expertise.suspensions.find(item => !item.resumed_on))
const minimumDate = computed(() => action.value === 'resume' ? openPause.value?.suspended_on ?? receivedOn.value : action.value === 'suspend' ? props.expertise.suspensions.reduce((date, item) => item.resumed_on && item.resumed_on > date ? item.resumed_on : date, receivedOn.value) : receivedOn.value)
const actionCode = computed(() => action.value === 'deadline' ? 'expertise.deadline.record' : `expertise.${action.value}`)
const authorized = computed(() => props.expertise.allowed_actions.includes(actionCode.value))
const recovering = computed(() => uncertain.value && Boolean(attempt.value))
const draft = computed(() => JSON.stringify([reason.value, factualOn.value, dueOn.value, kind.value, documentId.value]))
const dirty = computed(() => Boolean(action.value && (draft.value !== initialDraft.value || documentForm.value?.dirty || attempt.value)))
const confirmLeave = useDirtyGuard(() => dirty.value || saving.value, inject(routerKey, undefined))
const documentOptions = computed(() => {
  const documents = [props.expertise.basis_document, ...props.expertise.deadline_events.map(item => item.document)]
  const seen = new Set<string>()
  return documents.filter((item): item is BasisDocument => Boolean(item && !('restricted' in item)))
    .filter(item => {
      if (seen.has(item.id)) return false
      seen.add(item.id)
      return (kind.value !== 'agreement' || ['deadline_agreement', 'resolution', 'decision'].includes(item.kind)) && (item.source_kind === 'paper_original' || item.versions.length > 0)
    })
})
const documentKindOptions = computed<{ value: DocumentKind; label: string }[]>(() => kind.value === 'request'
  ? [{ value: 'deadline_request', label: 'Запрос срока' }]
  : [{ value: 'deadline_agreement', label: 'Подтверждение согласования срока' }, { value: 'resolution', label: 'Постановление' }, { value: 'decision', label: 'Определение' }])
const valid = computed(() => {
  if (!action.value || (!authorized.value && !recovering.value) || !reason.value.trim()) return false
  if (recovering.value) return true
  if (!factualOn.value || factualOn.value < minimumDate.value || factualOn.value > today()) return false
  if (action.value === 'deadline') {
    if (!dueOn.value || dueOn.value < receivedOn.value) return false
    if (kind.value === 'agreement' && !documentId.value) return false
    if (documentId.value && documentId.value !== 'new' && !documentOptions.value.some(item => item.id === documentId.value)) return false
  }
  return true
})
const conflictWithFreshVersion = computed(() => error.value instanceof ApiError && error.value.status === 409 && attempt.value && attempt.value.body.expected_version !== props.expertise.version)
function invalidateAttempt() { attempt.value = null; uncertain.value = false }
watch([() => reason.value.trim(), factualOn, dueOn, kind, documentId], invalidateAttempt, { flush: 'sync' })
watch(kind, value => { documentId.value = value === 'agreement' ? 'new' : '' }, { flush: 'sync' })
function start(value: Action) {
  action.value = value; reason.value = ''; factualOn.value = today(); dueOn.value = ''; kind.value = 'initial'; documentId.value = ''; error.value = null; invalidateAttempt()
  initialDraft.value = draft.value
}
function cancel() { if (!saving.value && confirmLeave()) { action.value = null; error.value = null; invalidateAttempt() } }
function acceptVersion() { invalidateAttempt(); error.value = null }
async function save() {
  if (!valid.value || saving.value || !action.value) return
  saving.value = true; error.value = null
  try {
    if (!attempt.value) {
      let evidence: string | null = documentId.value && documentId.value !== 'new' ? documentId.value : null
      if (action.value === 'deadline' && documentId.value === 'new') {
        if (!documentForm.value) return
        evidence = (await documentForm.value.persist()).id
      }
      const body: CommandBody = { expected_version: props.expertise.version, reason: reason.value.trim() }
      if (action.value === 'deadline') Object.assign(body, { kind: kind.value, recorded_on: factualOn.value, due_on: dueOn.value, document_id: evidence })
      else if (action.value === 'suspend') body.suspended_on = factualOn.value
      else body.resumed_on = factualOn.value
      attempt.value = { key: newCommandKey(), body }
    }
    const endpoint = action.value === 'deadline' ? 'deadline-events' : action.value
    const result = await api.request<{ event: { id: string }; expertise: Expertise }>(`/expertises/${props.expertise.id}/${endpoint}/`, { method: 'POST', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
    action.value = null; reason.value = ''; dueOn.value = ''; documentId.value = ''; invalidateAttempt()
    emit('updated', result.expertise)
  } catch (cause) {
    error.value = cause
    uncertain.value = Boolean(attempt.value) && (!(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response')
  } finally { saving.value = false }
}
function time(value: string) { return new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Krasnoyarsk', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) }
</script>
<template>
  <section data-production class="card stack-card">
    <div class="section-heading"><div><h2>Производство и сроки</h2><p class="muted compact">Календарный учёт по состоянию на {{ expertise.production.as_of }}</p></div><div v-if="!action" class="button-row"><button v-if="expertise.allowed_actions.includes('expertise.suspend')" data-production-suspend @click="start('suspend')">Приостановить</button><button v-if="expertise.allowed_actions.includes('expertise.resume')" data-production-resume class="button-primary" @click="start('resume')">Возобновить</button><button v-if="expertise.allowed_actions.includes('expertise.deadline.record')" data-production-deadline @click="start('deadline')">Записать срок</button></div></div>
    <dl class="work-facts"><div><dt>Календарные дни</dt><dd data-calendar-days>{{ expertise.production.calendar_days ?? 'Неизвестно' }}</dd></div><div><dt>Дни приостановки</dt><dd data-paused-days>{{ expertise.production.paused_days ?? 'Неизвестно' }}</dd></div><div><dt>Календарные дни без пауз</dt><dd data-active-days>{{ expertise.production.active_calendar_days ?? 'Неизвестно' }}</dd></div></dl>
    <p data-counted-through class="muted compact">{{ closed ? 'Учёт остановлен на подтверждённом окончании: ' : 'Дни учтены по: ' }}{{ expertise.production.counted_through || 'Неизвестно — подтверждённого окончания нет' }}.</p>
    <p class="muted compact">Счётчик не является юридическим или рабочим сроком. От поступления до {{ closed ? 'подтверждённого окончания' : 'даты расчёта' }} включительно; пауза [приостановка, возобновление), день возобновления активен. {{ closed ? 'Незавершённая пауза ограничивается окончанием работы; возобновление не создаётся.' : 'Открытая пауза включает дату расчёта.' }} Метод: <code>{{ expertise.production.method }}</code>.</p>
    <dl class="work-facts"><div><dt>Исходный срок</dt><dd data-initial-due>{{ expertise.production.initial_due_on || 'Неизвестен' }}</dd></div><div><dt>Согласованный срок</dt><dd>{{ expertise.production.agreed_due_on || 'Неизвестен' }}</dd></div><div><dt>Действующий срок</dt><dd data-current-due>{{ expertise.production.current_due_on || 'Неизвестен' }}</dd></div><div><dt>Последний запрошенный срок</dt><dd data-requested-due>{{ expertise.production.last_requested_due_on || 'Не запрашивался' }}</dd></div><div><dt>Календарные дни после срока</dt><dd>{{ expertise.production.overdue_calendar_days ?? 'Неизвестно' }}</dd></div></dl>
    <p class="muted compact">Запрос нового срока не меняет действующий срок и не снимается с контроля автоматически. Исходный срок и его уточнения сохраняются отдельными событиями.</p>
    <form v-if="action" data-production-form class="inset-form form-grid" @submit.prevent="save">
      <h3>{{ action === 'suspend' ? 'Приостановка производства' : action === 'resume' ? 'Возобновление производства' : 'Запись события срока' }}</h3>
      <ApiMessage :error="error" />
      <p v-if="recovering" class="muted compact">Ответ на команду не получен. Повторить ту же попытку можно с исходной версией и ключом; сервер вернёт сохранённый результат и свежую карточку.</p>
      <p v-else-if="!authorized" class="message message-error">Действие больше не разрешено для этой работы. Введённые данные сохранены в форме.</p>
      <p v-if="conflictWithFreshVersion" class="message message-error">Карточка обновлена, данные формы сохранены. Для новой попытки явно примените текущую версию или измените данные. <button type="button" :disabled="saving || !authorized" @click="acceptVersion">Применить версию {{ expertise.version }} к новой попытке</button></p>
      <fieldset class="form-grid" :disabled="saving || (!authorized && !recovering)">
        <label v-if="action === 'deadline'">Вид события<select v-model="kind" name="deadline_kind"><option v-for="(label, value) in labels" :key="value" :value="value">{{ label }}</option></select></label>
        <div class="form-columns"><label>{{ action === 'suspend' ? 'Дата приостановки' : action === 'resume' ? 'Дата возобновления' : 'Фактическая дата события' }}<input v-model="factualOn" :name="action === 'deadline' ? 'recorded_on' : action === 'suspend' ? 'suspended_on' : 'resumed_on'" type="date" :min="minimumDate" :max="today()" required /></label><label v-if="action === 'deadline'">{{ kind === 'request' ? 'Запрошенный срок исполнения' : 'Срок исполнения' }}<input v-model="dueOn" name="due_on" type="date" :min="receivedOn" required /></label></div>
        <label>Причина / основание<textarea v-model="reason" name="production_reason" rows="3" required /></label>
        <template v-if="action === 'deadline'">
          <label>{{ kind === 'agreement' ? 'Документ согласования (обязательно)' : 'Документ события (при наличии)' }}<select v-model="documentId" name="production_document"><option v-if="kind !== 'agreement'" value="">Без документа</option><option value="new">Подготовить новый документ</option><option v-for="document in documentOptions" :key="document.id" :value="document.id">{{ document.title || document.id }}</option></select></label>
          <BasisDocumentForm v-if="documentId === 'new'" :key="kind" ref="documentForm" :department-id="expertise.department.id" :busy="saving" :heading="kind === 'agreement' ? 'Документ согласования срока' : 'Документ события срока'" :kind-options="documentKindOptions" @changed="invalidateAttempt" />
          <p v-if="kind === 'agreement'" class="muted compact">Подтверждение: заявленный бумажный оригинал или сохранённая копия. Документ запроса не подтверждает согласование.</p>
        </template>
      </fieldset>
      <p class="muted compact">Фактические даты — от поступления до сегодняшнего дня учреждения (Asia/Krasnoyarsk). Для прошлого события укажите причину. Срок исполнения может быть будущим.</p>
      <div class="button-row"><button type="submit" class="button-primary" :formnovalidate="recovering" :disabled="saving || !valid">{{ saving ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : 'Сохранить событие' }}</button><button type="button" :disabled="saving" @click="cancel">Отмена</button></div>
    </form>
    <section data-suspension-history class="subsection"><h3>Приостановки и возобновления</h3><p v-if="expertise.historical && !expertise.historical.suspension_history_complete" class="muted compact">Полнота исторических приостановок неизвестна. Отсутствие записанных событий не означает отсутствие пауз.</p><div v-for="pause in expertise.suspensions" :key="pause.id" class="assignment-line"><strong>{{ pause.suspended_on }} → {{ pause.resumed_on || (closed ? expertise.production.counted_through ? `Ограничена окончанием ${expertise.production.counted_through}` : 'Окончание неизвестно; возобновление не подтверждено' : 'Открытая приостановка') }}</strong><p class="compact">{{ pause.reason }}</p><small>Приостановку внёс {{ pause.actor.full_name }} · {{ time(pause.created_at) }}</small><template v-if="pause.resumed_on"><p class="compact">{{ pause.resume_reason }}</p><small>Возобновление внёс {{ pause.resumed_by?.full_name || 'Неизвестно' }}{{ pause.resumed_recorded_at ? ` · ${time(pause.resumed_recorded_at)}` : '' }}</small></template></div><p v-if="!expertise.suspensions.length" class="muted compact">События приостановок пока не записаны.</p></section>
    <section data-deadline-history class="subsection"><h3>История сроков</h3><div v-for="event in expertise.deadline_events" :key="event.id" class="assignment-line"><strong>{{ labels[event.kind] }} · {{ event.recorded_on }}</strong><p class="compact">Срок исполнения: {{ event.due_on }} · {{ event.reason }}</p><small>Внёс {{ event.actor.full_name }} · {{ time(event.created_at) }}</small><BasisPreview v-if="event.document" :document="event.document" :heading="event.kind === 'agreement' ? 'Документ согласования срока' : 'Документ события срока'" empty-text="Документ не указан." /><p v-else class="muted compact">Документ не указан.</p></div><p v-if="!expertise.deadline_events.length" class="muted compact">Событий срока пока нет.</p></section>
  </section>
</template>
