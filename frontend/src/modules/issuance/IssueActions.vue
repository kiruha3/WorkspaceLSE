<script setup lang="ts">
import { computed, inject, reactive, ref } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError } from '../../api/client'
import { issueToday, type IssueOptions, type IssuePackage } from '../../api/issuance'
import type { DocumentKind } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import IssueDocumentPicker from './IssueDocumentPicker.vue'
import { useIssueAttempt } from './useIssueAttempt'
const props = defineProps<{ package: IssuePackage; options: IssueOptions }>()
const emit = defineEmits<{ updated: [value: IssuePackage] }>()
const session = useSessionStore(), action = ref<'check' | 'issue' | null>(null), baseVersion = ref(props.package.version), initial = ref(''), proofDepartment = ref(''), proofChanges = ref(0)
const fields = reactive({ reason: '', issued_on: '', method_id: '', recipient_name: '', recipient_basis: '', tracking: '', comment: '' })
const normalized = computed(() => ({ reason: fields.reason.trim(), issued_on: fields.issued_on, method_id: fields.method_id, recipient_name: fields.recipient_name.trim(), recipient_basis: fields.recipient_basis.trim(), tracking: fields.tracking.trim(), comment: fields.comment.trim() }))
const stamp = computed(() => JSON.stringify({ action: action.value, ...normalized.value, proofDepartment: proofDepartment.value, proofChanges: proofChanges.value }))
const { attempt, busy, error, recovering, reset, execute } = useIssueAttempt(stamp)
const picker = ref<InstanceType<typeof IssueDocumentPicker> | null>(null)
const proofKinds = [{ value: 'letter' as DocumentKind, label: 'Подтверждение выдачи' }]
const departments = computed(() => [...new Map(props.package.works.map(work => [work.department.id, work.department])).values()])
const authorized = computed(() => props.package.allowed_actions.includes(action.value === 'check' ? 'issue.check' : 'issue.confirm'))
const valid = computed(() => {
  if (recovering.value) return true
  if (!action.value || !authorized.value || !fields.reason.trim()) return false
  if (action.value === 'check') return props.package.readiness.can_check
  return props.package.readiness.can_issue && Boolean(fields.issued_on && fields.issued_on <= issueToday() && fields.method_id && fields.recipient_name.trim() && fields.recipient_basis.trim() && (!picker.value?.newDocument || proofDepartment.value))
})
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && baseVersion.value !== props.package.version)
const confirmLeave = useDirtyGuard(() => Boolean(action.value && (stamp.value !== initial.value || attempt.value || picker.value?.dirty)) || busy.value, inject(routerKey, undefined))
function start(value: 'check' | 'issue') { action.value = value; baseVersion.value = props.package.version; Object.assign(fields, { reason: '', issued_on: '', method_id: '', recipient_name: '', recipient_basis: '', tracking: '', comment: '' }); proofDepartment.value = ''; proofChanges.value = 0; reset(); initial.value = stamp.value }
function cancel() { if (!busy.value && confirmLeave()) { action.value = null; reset() } }
function acceptVersion() { baseVersion.value = props.package.version; reset() }
async function save() {
  if (!valid.value || !action.value) return
  const source: Record<string, unknown> = action.value === 'check' ? { expected_version: baseVersion.value, reason: fields.reason.trim() } : { expected_version: baseVersion.value, ...normalized.value, evidence_document_id: null }
  const command = action.value
  const response = await execute(`/issue-packages/${props.package.id}/${command}/`, async () => {
    if (command === 'issue') source.evidence_document_id = await picker.value!.persist()
    return source
  })
  if (response) { action.value = null; emit('updated', response.package) }
}
</script>
<template>
  <section class="card stack-card"><h2>Проверка и выдача</h2><div v-if="!action" class="button-row"><button v-if="package.allowed_actions.includes('issue.check')" data-start-package-check :disabled="!package.readiness.can_check" @click="start('check')">Проверить комплект</button><button v-if="package.allowed_actions.includes('issue.confirm')" data-start-issue class="button-primary" :disabled="!package.readiness.can_issue" @click="start('issue')">Записать фактическую выдачу</button><p v-if="!package.allowed_actions.some(item => ['issue.check','issue.confirm'].includes(item))" class="muted compact">Действий проверки и выдачи для этой записи не разрешено.</p></div>
    <form v-else data-issue-command class="inset-form form-grid" @submit.prevent="save"><h3>{{ action === 'check' ? 'Проверка состава и версий файлов' : 'Фактическая передача материалов' }}</h3><ApiMessage :error="error" /><p v-if="recovering" class="message">Ответ не получен. Повтор использует исходные данные, версию и ключ попытки; полномочия проверит сервер.</p><p v-else-if="!authorized" class="message message-error">Действие больше не разрешено. Введённые данные сохранены.</p><p v-if="conflict" class="message">Комплект обновлён, поля формы сохранены. <button data-accept-issue-version type="button" :disabled="busy || !authorized" @click="acceptVersion">Применить версию {{ package.version }} к новой попытке</button></p>
      <fieldset class="form-grid" :disabled="busy || (!authorized && !recovering)"><template v-if="action === 'issue'"><div class="form-columns"><label>Фактическая дата выдачи<input v-model="fields.issued_on" name="issued_on" type="date" :max="issueToday()" required /></label><label>Способ передачи<select v-model="fields.method_id" name="method_id" required><option value="">Выберите способ</option><option v-for="item in options.methods.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label></div><label>Получатель<input v-model="fields.recipient_name" name="recipient_name" required /></label><label>Основание получения<input v-model="fields.recipient_basis" name="recipient_basis" required /></label><label>Трек / идентификатор отправления<input v-model="fields.tracking" name="issue_tracking" /></label><label>Комментарий<textarea v-model="fields.comment" name="issue_comment" /></label><label v-if="session.can('documents.upload')">Отдел нового документа подтверждения<select v-model="proofDepartment" name="proof_department_id" :required="picker?.newDocument"><option value="">Выберите при создании подтверждения</option><option v-for="item in departments" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><IssueDocumentPicker ref="picker" :package-id="package.id" kind="other" :department-id="proofDepartment" :kind-options="proofKinds" :busy="busy" heading="Подтверждение выдачи" @changed="proofChanges++" /><p class="muted compact">Записывается состоявшаяся передача. Счёт не означает оплату. Автоматической отправки писем нет.</p></template><p v-else class="muted">Проверка сохранит состав работ, окончаний и принятые версии файлов. Факт выдачи записывается отдельно.</p><label>Причина / основание записи<textarea v-model="fields.reason" name="issue_command_reason" required /></label></fieldset><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="recovering" :disabled="busy || !valid">{{ busy ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : action === 'check' ? 'Подтвердить проверку' : 'Сохранить факт выдачи' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
    </form>
  </section>
</template>
