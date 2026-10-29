<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { OrgAssignment, Reference } from '../../api/types'
import { useApi } from '../../api/client'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const props = defineProps<{ employeeId: string; assignments: OrgAssignment[] }>()
const emit = defineEmits<{ updated: [assignment: OrgAssignment] }>()
const api = useApi(), session = useSessionStore(), controller = new AbortController()
const departments = ref<Reference[]>([]), positions = ref<Reference[]>([]), loading = ref(false), saving = ref(false)
const adding = ref(false), departmentId = ref(''), positionId = ref(''), validFrom = ref(''), validTo = ref(''), reason = ref('')
const ending = ref<OrgAssignment | null>(null), endDate = ref(''), endReason = ref('')
const error = ref<unknown>(null), loadError = ref<unknown>(null), success = ref('')
const dirty = computed(() => (adding.value && Boolean(departmentId.value || positionId.value || validFrom.value || validTo.value || reason.value)) || (ending.value !== null && Boolean(endDate.value || endReason.value)))
defineExpose({ dirty, busy: saving })
function toggleAdd() {
  if (adding.value && dirty.value && !window.confirm('Свернуть несохранённое кадровое назначение?')) return
  adding.value = !adding.value
}
async function create() {
  if (saving.value || !session.can('employees.org_assignments.manage')) return
  error.value = null; success.value = ''
  if (validFrom.value && validTo.value && validFrom.value > validTo.value) { error.value = new Error('Окончание назначения не может быть раньше начала.'); return }
  saving.value = true
  try {
    const assignment = await api.request<OrgAssignment>(`/employees/${props.employeeId}/org-assignments/`, { method: 'POST', body: { department_id: departmentId.value, position_id: positionId.value, valid_from: validFrom.value || null, valid_to: validTo.value || null, reason: reason.value.trim() } })
    emit('updated', assignment); adding.value = false; departmentId.value = ''; positionId.value = ''; validFrom.value = ''; validTo.value = ''; reason.value = ''
    success.value = 'Кадровое назначение сохранено сервером.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function startEnd(assignment: OrgAssignment) {
  if (ending.value && (endDate.value || endReason.value) && !window.confirm('Заменить несохранённое прекращение назначения?')) return
  ending.value = assignment; endDate.value = ''; endReason.value = ''; error.value = null; success.value = ''
}
async function end() {
  if (!ending.value || saving.value || !session.can('employees.org_assignments.manage')) return
  error.value = null; success.value = ''; saving.value = true
  try {
    const assignment = await api.request<OrgAssignment>(`/employee-org-assignments/${ending.value.id}/`, { method: 'PATCH', body: { expected_version: ending.value.version, valid_to: endDate.value, reason: endReason.value.trim() } })
    emit('updated', assignment); ending.value = null; endDate.value = ''; endReason.value = ''; success.value = 'Окончание назначения сохранено сервером.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function cancelEnd() {
  if ((endDate.value || endReason.value) && !window.confirm('Отменить несохранённое прекращение назначения?')) return
  ending.value = null; endDate.value = ''; endReason.value = ''
}
onMounted(async () => {
  if (!session.can('employees.org_assignments.manage')) return
  loading.value = true
  const results = await Promise.allSettled([
    api.allPages<Reference>('/references/departments/', controller.signal).then(items => { departments.value = items }),
    api.allPages<Reference>('/references/positions/', controller.signal).then(items => { positions.value = items }),
  ])
  const failure = results.find(result => result.status === 'rejected')
  if (failure?.status === 'rejected' && !controller.signal.aborted) loadError.value = failure.reason
  loading.value = false
})
onBeforeUnmount(() => controller.abort())
</script>
<template>
  <section><div class="section-heading"><h3>Должности и подразделения</h3><button v-if="session.can('employees.org_assignments.manage')" data-add-org :disabled="saving" @click="toggleAdd">Добавить назначение</button></div><ApiMessage :error="loadError" /><ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <div v-for="assignment in assignments" :key="assignment.id" class="org-line"><div class="section-heading"><div><strong>{{ assignment.position.name }}</strong><p>{{ assignment.department.name }}</p></div><button v-if="session.can('employees.org_assignments.manage') && !assignment.valid_to" :data-end-org="assignment.id" :disabled="saving" @click="startEnd(assignment)">Указать окончание</button></div><small>{{ assignment.valid_from ?? 'Начало не указано' }} — {{ assignment.valid_to ?? 'окончание не указано' }}</small><small class="block">{{ assignment.reason || 'Основание не указано' }} · версия {{ assignment.version }}</small></div><p v-if="!assignments.length" class="muted">Кадровые назначения не указаны.</p>
    <form v-if="adding" data-org-create-form class="inset-form form-grid" @submit.prevent="create"><h4>Новое кадровое назначение</h4><fieldset :disabled="saving || loading"><div class="form-grid"><label>Подразделение<select v-model="departmentId" name="org_department" required><option value="">Выберите подразделение</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Должность<select v-model="positionId" name="org_position" required><option value="">Выберите должность</option><option v-for="item in positions.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><div class="form-columns"><label>Начало, если известно<input v-model="validFrom" name="org_valid_from" type="date" /></label><label>Окончание, если известно<input v-model="validTo" type="date" /></label></div><label>Основание<textarea v-model="reason" name="org_reason" required rows="2" /></label><p class="muted compact">Должность не выдаёт роли или экспертную квалификацию автоматически.</p><button class="button-primary align-start" :disabled="saving || !departmentId || !positionId || !reason.trim()">Сохранить назначение</button></div></fieldset></form>
    <form v-if="ending" data-org-end-form class="inset-form form-grid" @submit.prevent="end"><h4>Окончание назначения: {{ ending.position.name }}</h4><label>Фактическая дата окончания<input v-model="endDate" name="org_end_date" type="date" required :disabled="saving" /></label><label>Основание<textarea v-model="endReason" name="org_end_reason" required rows="2" :disabled="saving" /></label><div class="button-row"><button class="button-primary" :disabled="saving || !endDate || !endReason.trim()">Сохранить окончание</button><button type="button" :disabled="saving" @click="cancelEnd">Отмена</button></div></form>
  </section>
</template>
