<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useApi } from '../../api/client'
import type { Access, EmployeeRole, Reference, Role, Scope } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const props = defineProps<{ employeeId: string }>()
const api = useApi(), session = useSessionStore()
const assignments = ref<EmployeeRole[]>([]), roles = ref<Role[]>([]), departments = ref<Reference[]>([])
const effective = ref<Access | null>(null), error = ref<unknown>(null), loadError = ref<unknown>(null)
const success = ref(''), loading = ref(true), saving = ref(false)
const roleId = ref(''), scopeLimit = ref<Scope | ''>(''), departmentIds = ref<string[]>([]), validFrom = ref(''), validTo = ref(''), reason = ref('')
const ending = ref<EmployeeRole | null>(null), endReason = ref('')
const dirty = computed(() => Boolean(roleId.value || scopeLimit.value || departmentIds.value.length || validFrom.value || validTo.value || reason.value || (ending.value && endReason.value)))
const controller = new AbortController()
const scopeLabels: Record<Scope, string> = { own: 'Свои', departments: 'Выбранные отделы', institution: 'Учреждение' }
defineExpose({ dirty })
async function loadAccess() {
  if (session.can('access.effective.view')) effective.value = await api.request<Access>(`/employees/${props.employeeId}/effective-access/`, { signal: controller.signal })
}
async function assign() {
  if (saving.value || !session.can('access.roles.assign')) return
  error.value = null; success.value = ''
  if (!roleId.value || !scopeLimit.value || !reason.value.trim()) { error.value = new Error('Выберите роль, область и укажите основание.'); return }
  if (scopeLimit.value === 'departments' && !departmentIds.value.length) { error.value = new Error('Выберите хотя бы один отдел. Пустой список не даёт доступа ко всему учреждению.'); return }
  if (validFrom.value && validTo.value && validFrom.value > validTo.value) { error.value = new Error('Окончание действия не может быть раньше начала.'); return }
  saving.value = true
  try {
    const assignment = await api.request<EmployeeRole>(`/employees/${props.employeeId}/roles/`, { method: 'POST', body: { role_id: roleId.value, scope_limit: scopeLimit.value, department_ids: scopeLimit.value === 'departments' ? departmentIds.value : [], valid_from: validFrom.value || null, valid_to: validTo.value || null, reason: reason.value.trim() } })
    assignments.value.push(assignment)
    roleId.value = ''; scopeLimit.value = ''; departmentIds.value = []; validFrom.value = ''; validTo.value = ''; reason.value = ''
    success.value = 'Роль назначена сервером. Другие назначения сохранены.'
    try { await loadAccess() } catch (cause) { loadError.value = cause }
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function startEnd(assignment: EmployeeRole) {
  if (ending.value && endReason.value && !window.confirm('Заменить несохранённое прекращение роли?')) return
  ending.value = assignment; endReason.value = ''; error.value = null; success.value = ''
}
async function endRole() {
  if (!ending.value || saving.value || !session.can('access.roles.assign')) return
  error.value = null; success.value = ''; saving.value = true
  try {
    const assignment = await api.request<EmployeeRole>(`/employee-roles/${ending.value.id}/`, { method: 'PATCH', body: { expected_version: ending.value.version, is_active: false, reason: endReason.value.trim() } })
    assignments.value = assignments.value.map(item => item.id === assignment.id ? assignment : item)
    ending.value = null; endReason.value = ''; success.value = 'Назначение роли прекращено сервером. Остальные роли сохранены.'
    try { await loadAccess() } catch (cause) { loadError.value = cause }
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function cancelEnd() {
  if (endReason.value && !window.confirm('Отменить несохранённое прекращение роли?')) return
  ending.value = null; endReason.value = ''
}
onMounted(async () => {
  const tasks: Promise<void>[] = []
  if (session.can('access.roles.view') || session.can('access.roles.assign')) tasks.push(api.request<EmployeeRole[]>(`/employees/${props.employeeId}/roles/`, { signal: controller.signal }).then(result => { assignments.value = result }))
  if (session.can('access.roles.assign')) {
    tasks.push(api.allPages<Role>('/roles/', controller.signal).then(result => { roles.value = result }))
    tasks.push(api.allPages<Reference>('/references/departments/', controller.signal).then(result => { departments.value = result }))
  }
  tasks.push(loadAccess())
  const results = await Promise.allSettled(tasks)
  const failed = results.find(result => result.status === 'rejected')
  if (failed?.status === 'rejected' && !controller.signal.aborted) loadError.value = failed.reason
  loading.value = false
})
onBeforeUnmount(() => controller.abort())
</script>
<template>
  <section class="subsection"><div class="section-heading"><div><h3>Роли и доступ</h3><p class="muted compact">Несколько назначений объединяют разрешения по каждому действию.</p></div></div>
    <ApiMessage :error="loadError" /><ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p><p v-if="loading" class="state">Загрузка доступа…</p>
    <div v-else class="table-scroll"><table><thead><tr><th>Роль</th><th>Ограничение</th><th>Период</th><th>Основание</th><th>Действие</th></tr></thead><tbody>
      <tr v-for="assignment in assignments" :key="assignment.id" data-assignment><td><strong>{{ assignment.role.name }}</strong><small>{{ assignment.is_active ? 'Активное назначение' : 'Назначение прекращено' }}</small><small>Версия {{ assignment.version }}</small></td><td>{{ scopeLabels[assignment.scope_limit] }}<small v-if="assignment.scope_limit === 'departments'">{{ assignment.department_ids.map(id => departments.find(d => d.id === id)?.name ?? id).join(', ') || 'Отделы не выбраны: доступа нет' }}</small></td><td>{{ assignment.valid_from ?? 'Начало не задано' }}<small>до {{ assignment.valid_to ?? 'даты не задано' }}</small></td><td>{{ assignment.reason || 'Не указано' }}</td><td><button v-if="assignment.is_active && session.can('access.roles.assign')" :data-end-role="assignment.id" :disabled="saving" @click="startEnd(assignment)">Прекратить роль</button><span v-else class="muted">—</span></td></tr>
      <tr v-if="!assignments.length"><td colspan="5" class="state">Назначенных ролей нет.</td></tr>
    </tbody></table></div>
    <form v-if="ending" data-end-role-form class="inset-form form-grid" @submit.prevent="endRole"><h4>Прекратить роль «{{ ending.role.name }}»</h4><label>Основание<textarea v-model="endReason" name="role_end_reason" rows="2" required :disabled="saving" /></label><div class="button-row"><button class="button-primary" :disabled="saving || !endReason.trim()">Подтвердить прекращение</button><button type="button" :disabled="saving" @click="cancelEnd">Отмена</button></div></form>
    <form v-if="session.can('access.roles.assign')" data-assign-role class="inset-form form-grid" @submit.prevent="assign"><h4>Назначить дополнительную роль</h4><fieldset :disabled="saving || loading"><div class="form-columns"><label>Роль<select v-model="roleId" name="assignment_role" required><option value="">Выберите роль</option><option v-for="role in roles.filter(r => r.is_active)" :key="role.id" :value="role.id">{{ role.name }}</option></select></label><label>Максимальная область назначения<select v-model="scopeLimit" name="scope_limit" required><option value="">Выберите явно</option><option value="own">Свои</option><option value="departments">Выбранные отделы</option><option value="institution">Учреждение</option></select></label><label v-if="scopeLimit === 'departments'">Подразделения<select v-model="departmentIds" name="assignment_department" multiple size="3"><option v-for="department in departments.filter(d => d.is_active)" :key="department.id" :value="department.id">{{ department.code }} · {{ department.name }}</option></select><small>Пустой набор отделов не предоставляет доступ.</small></label><label>Начало, если задано<input v-model="validFrom" type="date" /></label><label>Окончание, если задано<input v-model="validTo" type="date" /></label></div><label>Основание назначения<textarea v-model="reason" name="assignment_reason" required rows="2" /></label><p class="muted compact">Ограничение может сузить права роли. Квалификация и кадровая должность остаются отдельными сведениями.</p><button class="button-primary" :disabled="saving">{{ saving ? 'Назначение…' : 'Назначить роль' }}</button></fieldset></form>
    <section v-if="effective" class="subsection"><div class="section-heading"><h4>Эффективные права</h4><button @click="loadAccess().catch(cause => loadError = cause)">Проверить снова</button></div><p class="muted compact">Сервер проверяет предметные условия каждой операции дополнительно.</p><div class="table-scroll"><table><thead><tr><th>Действие</th><th>Область и источник</th></tr></thead><tbody><tr v-for="(grants, code) in effective" :key="code"><td><code>{{ code }}</code></td><td><p v-for="grant in grants" :key="grant.assignment_id" class="cell-line">{{ scopeLabels[grant.scope] }} · {{ grant.role_name }}<small>Ограничение: {{ scopeLabels[grant.scope_limit] }}<template v-if="grant.department_ids.length"> · {{ grant.department_ids.map(id => departments.find(d => d.id === id)?.name ?? id).join(', ') }}</template></small></p></td></tr><tr v-if="!Object.keys(effective).length"><td colspan="2" class="state">Эффективных прав нет.</td></tr></tbody></table></div></section>
  </section>
</template>
