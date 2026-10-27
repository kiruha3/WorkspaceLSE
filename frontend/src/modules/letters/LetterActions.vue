<script setup lang="ts">
import { computed, inject, reactive, ref } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError } from '../../api/client'
import { institutionToday, type Letter, type LetterOptions } from '../../api/letters'
import type { BasisDocument, DocumentKind } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useLetterAttempt } from './useLetterAttempt'
const props = defineProps<{ letter: Letter; options: LetterOptions }>()
const emit = defineEmits<{ updated: [letter: Letter] }>()
type Action = 'register' | 'send' | 'receive' | 'deliver' | 'assign' | 'control' | 'deadline' | 'close' | 'reopen'
const definitions: { value: Action; label: string; permission: string; endpoint: string }[] = [
  { value: 'register', label: 'Зарегистрировать', permission: 'letters.register', endpoint: 'register' },
  { value: 'send', label: 'Записать фактическую отправку', permission: 'letters.mark_sent', endpoint: 'mark-sent' },
  { value: 'receive', label: 'Подтвердить получение', permission: 'letters.mark_received', endpoint: 'mark-received' },
  { value: 'deliver', label: 'Подтвердить доставку адресату', permission: 'letters.mark_delivered', endpoint: 'mark-delivered' },
  { value: 'assign', label: 'Назначить ответственного', permission: 'control.assign', endpoint: 'assign' },
  { value: 'control', label: 'Поставить на контроль', permission: 'control.assign', endpoint: 'control' },
  { value: 'deadline', label: 'Изменить срок контроля', permission: 'control.assign', endpoint: 'control/deadline' },
  { value: 'close', label: 'Закрыть контроль', permission: 'control.close', endpoint: 'control/close' },
  { value: 'reopen', label: 'Возобновить контроль', permission: 'control.reopen', endpoint: 'control/reopen' },
]
const session = useSessionStore(), action = ref<Action | null>(null), initial = ref('')
const fields = reactive({ reason: '', date: '', journal_id: '', registration_number: '', channel_id: '', recipient_ids: [] as string[], tracking: '', comment: '', evidence: '', dispatch_id: '', recipient_id: '', responsible_id: '', due_on: '', due_basis: '', closure_reason_id: '', reply_id: '' })
const documentForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const stamp = computed(() => JSON.stringify({ action: action.value, ...fields, reason: fields.reason.trim(), registration_number: fields.registration_number.trim(), tracking: fields.tracking.trim(), comment: fields.comment.trim(), due_basis: fields.due_basis.trim(), recipient_ids: [...fields.recipient_ids].sort() }))
const { attempt, busy, error, recovering, reset, execute } = useLetterAttempt(stamp)
const selected = computed(() => definitions.find(item => item.value === action.value))
const authorized = computed(() => Boolean(selected.value && props.letter.allowed_actions.includes(selected.value.permission)))
const available = computed(() => definitions.filter(item => props.letter.allowed_actions.includes(item.permission) && (item.value !== 'control' || !props.letter.control) && (item.value !== 'deadline' || props.letter.control) && (item.value !== 'close' || props.letter.control?.status === 'open') && (item.value !== 'reopen' || props.letter.control?.status === 'closed')))
const journals = computed(() => props.options.journals.filter(item => item.is_active && item.direction === props.letter.direction && (!item.department_id || item.department_id === props.letter.department?.id)))
const evidenceOptions = computed(() => props.letter.attachments.map(item => item.document).filter((item): item is BasisDocument => Boolean(item && !('restricted' in item))))
const usesEvidence = computed(() => ['send', 'receive', 'deliver'].includes(action.value ?? ''))
const dispatch = computed(() => props.letter.dispatches.find(item => item.id === fields.dispatch_id))
const recipientOptions = computed(() => action.value === 'deliver' ? props.letter.content.recipients.filter(item => dispatch.value?.recipient_ids.includes(item.id)) : props.letter.content.recipients)
const dateName = computed(() => ({ register: 'registered_on', send: 'sent_on', receive: 'received_on', deliver: 'delivered_on', control: 'opened_on', close: 'closed_on', reopen: 'reopened_on' }[action.value as string] ?? ''))
const closureRule = computed(() => props.options.closure_reasons.find(item => item.id === fields.closure_reason_id)?.rule)
const replyOptions = computed(() => props.letter.replies.filter(item => item.reply_completeness === 'final' && (closureRule.value === 'reply_sent' ? item.direction === 'outgoing' && item.state === 'sent' : item.direction === 'incoming' && item.state !== 'draft')))
const valid = computed(() => {
  if (!action.value || (!authorized.value && !recovering.value)) return false
  if (recovering.value) return true
  if (!fields.reason.trim()) return false
  if (dateName.value && (!fields.date || fields.date > institutionToday())) return false
  if (action.value === 'register') return Boolean(fields.journal_id && fields.registration_number.trim())
  if (action.value === 'send') return Boolean(fields.channel_id && fields.recipient_ids.length)
  if (action.value === 'deliver') return Boolean(fields.dispatch_id && fields.recipient_id)
  if (action.value === 'assign') return Boolean(fields.responsible_id)
  if (['control', 'deadline'].includes(action.value)) return !fields.due_on || Boolean(fields.due_basis.trim())
  if (action.value === 'close') return Boolean(fields.closure_reason_id && (['reply_sent', 'reply_received'].includes(closureRule.value ?? '') ? fields.reply_id : fields.comment.trim()))
  return true
})
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && attempt.value && attempt.value.body.expected_version !== props.letter.version)
const confirmLeave = useDirtyGuard(() => Boolean(action.value && (stamp.value !== initial.value || attempt.value || documentForm.value?.dirty)) || busy.value, inject(routerKey, undefined))
function start(value: Action) { action.value = value; Object.assign(fields, { reason: '', date: '', journal_id: '', registration_number: '', channel_id: '', recipient_ids: [], tracking: '', comment: '', evidence: '', dispatch_id: '', recipient_id: '', responsible_id: '', due_on: '', due_basis: '', closure_reason_id: '', reply_id: '' }); reset(); initial.value = stamp.value }
function cancel() { if (!busy.value && confirmLeave()) { action.value = null; reset() } }
const kinds = [{ value: 'letter' as DocumentKind, label: 'Документ переписки' }]
async function save() {
  if (!valid.value || !selected.value) return
  const result = await execute(`/letters/${props.letter.id}/${selected.value.endpoint}/`, async () => {
    const body: Record<string, unknown> = { expected_version: props.letter.version, reason: fields.reason.trim() }
    if (dateName.value) body[dateName.value] = fields.date
    if (action.value === 'register') Object.assign(body, { journal_id: fields.journal_id, registration_number: fields.registration_number.trim() })
    if (action.value === 'send') Object.assign(body, { channel_id: fields.channel_id, recipient_ids: [...fields.recipient_ids].sort(), tracking: fields.tracking.trim(), comment: fields.comment.trim() })
    if (action.value === 'deliver') Object.assign(body, { dispatch_id: fields.dispatch_id, recipient_id: fields.recipient_id })
    if (usesEvidence.value) body.evidence_document_id = fields.evidence === 'new' ? (await documentForm.value!.persist()).id : fields.evidence || null
    if (action.value === 'assign') body.responsible_id = fields.responsible_id
    if (action.value === 'control' || action.value === 'deadline') Object.assign(body, { due_on: fields.due_on || null, due_basis: fields.due_basis.trim() })
    if (action.value === 'close') Object.assign(body, { closure_reason_id: fields.closure_reason_id, reply_id: fields.reply_id || null, comment: fields.comment.trim() })
    if (action.value === 'reopen') body.comment = fields.comment.trim()
    return body
  })
  if (result) { action.value = null; emit('updated', result.letter) }
}
</script>
<template>
  <section class="card stack-card" data-letter-actions><h2>Действия с письмом</h2>
    <div v-if="!action" class="button-row"><button v-for="item in available" :key="item.value" :data-action="item.value" @click="start(item.value)">{{ item.label }}</button><p v-if="!available.length" class="muted compact">Сервер не разрешил действий с этой записью.</p></div>
    <form v-else data-letter-command class="inset-form form-grid" @submit.prevent="save"><h3>{{ selected?.label }}</h3><ApiMessage :error="error" />
      <p v-if="recovering" class="message">Ответ не получен. Повтор использует исходные данные, версию и ключ попытки.</p><p v-else-if="!authorized" class="message message-error">Действие больше не разрешено. Введённые данные сохранены.</p>
      <p v-if="conflict" class="message">Серверная версия обновилась. Данные формы сохранены. <button data-accept-command-version type="button" :disabled="busy || !authorized" @click="reset">Применить версию {{ letter.version }} к новой попытке</button></p>
      <fieldset class="form-grid" :disabled="busy || (!authorized && !recovering)">
        <label v-if="dateName">Фактическая дата<input v-model="fields.date" :name="dateName" type="date" :max="institutionToday()" required /></label>
        <template v-if="action === 'register'"><label>Журнал<select v-model="fields.journal_id" name="journal_id" required><option value="">Выберите журнал</option><option v-for="item in journals" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Внутренний регистрационный номер<input v-model="fields.registration_number" name="registration_number" required /></label><p class="muted compact">Номер вводится вручную. Внешний номер сохраняется отдельно.</p></template>
        <template v-if="action === 'send'"><label>Способ фактической отправки<select v-model="fields.channel_id" name="channel_id" required><option value="">Выберите способ</option><option v-for="item in options.channels.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><fieldset><legend>Адресаты этой отправки</legend><label v-for="item in recipientOptions" :key="item.id" class="check-label"><input v-model="fields.recipient_ids" type="checkbox" name="recipient_ids" :value="item.id" />{{ item.name }} {{ item.address }} {{ item.email }}</label></fieldset><label>Трек / идентификатор<input v-model="fields.tracking" name="tracking" /></label><p class="muted compact">Запись факта отправки. Доставка и закрытие контроля подтверждаются отдельно.</p></template>
        <template v-if="action === 'deliver'"><label>Отправка<select v-model="fields.dispatch_id" name="dispatch_id" required @change="fields.recipient_id = ''"><option value="">Выберите отправку</option><option v-for="item in letter.dispatches" :key="item.id" :value="item.id">{{ item.sent_on }} · {{ item.channel.name }} · {{ item.tracking }}</option></select></label><label>Получивший адресат<select v-model="fields.recipient_id" name="recipient_id" required><option value="">Выберите адресата</option><option v-for="item in recipientOptions" :key="item.id" :value="item.id">{{ item.name }}</option></select></label></template>
        <label v-if="action === 'assign'">Новый ответственный<select v-model="fields.responsible_id" name="responsible_id" required><option value="">Выберите сотрудника</option><option v-for="item in options.employees" :key="item.id" :value="item.id">{{ item.full_name }}</option></select></label>
        <template v-if="action === 'control' || action === 'deadline'"><label>Срок, если известен<input v-model="fields.due_on" name="due_on" type="date" /></label><label>Основание срока<textarea v-model="fields.due_basis" name="due_basis" :required="Boolean(fields.due_on)" /></label><p class="muted compact">Неизвестный срок останется неизвестным. Смена срока не возобновляет закрытый контроль.</p></template>
        <template v-if="action === 'close'"><label>Основание закрытия<select v-model="fields.closure_reason_id" name="closure_reason_id" required @change="fields.reply_id = ''"><option value="">Выберите основание</option><option v-for="item in options.closure_reasons.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label v-if="closureRule === 'reply_sent' || closureRule === 'reply_received'">Завершающий ответ<select v-model="fields.reply_id" name="reply_id" required><option value="">Выберите ответ</option><option v-for="item in replyOptions" :key="item.id" :value="item.id">{{ item.registration_number }} · {{ item.subject }}</option></select></label></template>
        <label v-if="['send','close','reopen'].includes(action)">Комментарий<textarea v-model="fields.comment" name="comment" :required="action === 'close' && !['reply_sent','reply_received'].includes(closureRule ?? '')" /></label>
        <template v-if="usesEvidence"><label>Документ подтверждения<select v-model="fields.evidence" name="evidence_document_id"><option value="">Без документа</option><option v-for="item in evidenceOptions" :key="item.id" :value="item.id">{{ item.title || item.id }}</option><option v-if="session.can('documents.upload')" value="new">Подготовить новый документ</option></select></label><BasisDocumentForm v-if="fields.evidence === 'new' && session.can('documents.upload')" ref="documentForm" heading="Документ подтверждения" saved-note="Факт переписки сохраняется отдельно." :kind-options="kinds" :department-id="letter.department?.id ?? ''" :busy="busy" @changed="reset" /></template>
        <label>Причина / основание записи<textarea v-model="fields.reason" name="command_reason" required /></label>
      </fieldset><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="recovering" :disabled="busy || !valid">{{ busy ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : 'Сохранить факт' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
    </form>
  </section>
</template>
