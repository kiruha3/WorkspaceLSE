<script setup lang="ts">
import { computed, inject, onMounted, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { useApi } from '../../api/client'
import type { Employee, EmployeeSpecialty, OrgAssignment, Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import EmployeeAccess from './EmployeeAccess.vue'
import EmployeeAccount from './EmployeeAccount.vue'
import EmployeeOrganization from './EmployeeOrganization.vue'

const props = defineProps<{ employee: Employee }>()
const emit = defineEmits<{ updated: [employee: Employee] }>()
const api = useApi(), session = useSessionStore()
const fullName = ref(props.employee.full_name), active = ref(props.employee.is_active)
const metadataVersion = ref(props.employee.version), originalName = ref(props.employee.full_name), originalActive = ref(props.employee.is_active)
const error = ref<unknown>(null), success = ref(''), saving = ref(false)
const specialties = ref<Reference[]>([]), refsError = ref<unknown>(null)
const addingSpecialty = ref(false), specialtyId = ref(''), status = ref('training'), started = ref(''), basis = ref(''), validUntil = ref('')
const qualifying = ref<EmployeeSpecialty | null>(null), qualifiedAt = ref(''), qualificationBasis = ref(''), qualificationValidUntil = ref('')
const access = ref<InstanceType<typeof EmployeeAccess> | null>(null)
const account = ref<InstanceType<typeof EmployeeAccount> | null>(null)
const organization = ref<InstanceType<typeof EmployeeOrganization> | null>(null)
const metadataDirty = computed(() => fullName.value !== originalName.value || active.value !== originalActive.value)
const qualificationDirty = computed(() => qualifying.value !== null && Boolean(qualifiedAt.value || qualificationBasis.value || qualificationValidUntil.value !== (qualifying.value.valid_until ?? '')))
const dirty = computed(() => metadataDirty.value || (addingSpecialty.value && Boolean(specialtyId.value || started.value || basis.value || validUntil.value)) || qualificationDirty.value || Boolean(access.value?.dirty || account.value?.dirty || organization.value?.dirty))
useDirtyGuard(() => dirty.value, inject(routerKey, undefined))
defineExpose({ dirty })
function acceptMetadata(employee: Employee) {
  fullName.value = employee.full_name; active.value = employee.is_active
  originalName.value = employee.full_name; originalActive.value = employee.is_active; metadataVersion.value = employee.version
}
watch(() => props.employee, employee => { if (!metadataDirty.value) acceptMetadata(employee) })
async function refresh() {
  const employee = await api.request<Employee>(`/employees/${props.employee.id}/`)
  emit('updated', employee)
  return employee
}
function updateOrganization(assignment: OrgAssignment) {
  const exists = props.employee.org_assignments.some(item => item.id === assignment.id)
  emit('updated', { ...props.employee, org_assignments: exists ? props.employee.org_assignments.map(item => item.id === assignment.id ? assignment : item) : [...props.employee.org_assignments, assignment] })
}
async function saveDetails() {
  if (saving.value) return
  saving.value = true; error.value = null; success.value = ''
  try {
    const employee = await api.request<Employee>(`/employees/${props.employee.id}/`, { method: 'PATCH', body: { expected_version: metadataVersion.value, ...(session.can('employees.update') && fullName.value !== originalName.value ? { full_name: fullName.value.trim() } : {}), ...(session.can('employees.deactivate') && active.value !== originalActive.value ? { is_active: active.value } : {}) } })
    emit('updated', employee); acceptMetadata(employee); success.value = 'Сведения сотрудника сохранены сервером.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
async function addSpecialty() {
  if (saving.value) return
  saving.value = true; error.value = null; success.value = ''
  try {
    await api.request(`/employees/${props.employee.id}/specialties/`, { method: 'POST', body: { specialty_id: specialtyId.value, status: status.value, training_started_at: started.value || null, valid_until: validUntil.value || null, basis: basis.value } })
    addingSpecialty.value = false; specialtyId.value = ''; started.value = ''; validUntil.value = ''; basis.value = ''
    success.value = 'Специальность сохранена сервером.'
    await refresh()
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function startQualify(specialty: EmployeeSpecialty) {
  if (qualificationDirty.value && !window.confirm('Заменить несохранённую форму подтверждения?')) return
  qualifying.value = specialty; qualifiedAt.value = ''; qualificationBasis.value = ''; qualificationValidUntil.value = specialty.valid_until ?? ''; error.value = null; success.value = ''
}
async function qualify() {
  if (!qualifying.value || saving.value || !qualificationBasis.value.trim() || !session.can('specialties.qualify')) return
  saving.value = true; error.value = null; success.value = ''
  try {
    const specialty = await api.request<EmployeeSpecialty>(`/employee-specialties/${qualifying.value.id}/qualify/`, { method: 'POST', body: { expected_version: qualifying.value.version, qualified_at: qualifiedAt.value || null, ...(qualificationValidUntil.value !== (qualifying.value.valid_until ?? '') ? {valid_until:qualificationValidUntil.value || null} : {}), basis: qualificationBasis.value.trim() } })
    emit('updated', { ...props.employee, specialties: props.employee.specialties.map(item => item.id === specialty.id ? specialty : item) })
    qualifying.value = null; qualifiedAt.value = ''; qualificationBasis.value = ''; success.value = 'Квалификация подтверждена сервером.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
async function reload() {
  if (dirty.value && !window.confirm('Загрузить серверную версию и заменить изменения этой карточки?')) return
  try {
    const employee = await refresh(); acceptMetadata(employee)
    qualifying.value = null; addingSpecialty.value = false; error.value = null; success.value = ''
  } catch (cause) { error.value = cause }
}
onMounted(async () => {
  if (session.can('specialties.training.manage')) {
    try { specialties.value = await api.allPages<Reference>('/references/specialties/') }
    catch (cause) { refsError.value = cause }
  }
})
</script>

<template>
  <section class="card employee-card">
    <div class="section-heading"><div><p class="eyebrow">Карточка сотрудника · версия {{ employee.version }}</p><h2>{{ employee.full_name }}</h2></div><div class="button-row"><span v-if="dirty" class="badge badge-amber">Есть изменения</span><button :disabled="saving" @click="reload">Обновить карточку</button></div></div>
    <ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <div class="detail-columns"><section><h3>Общие сведения</h3><form class="form-grid" @submit.prevent="saveDetails"><label>ФИО<input v-model="fullName" required :disabled="!session.can('employees.update') || saving" /></label><label class="check-label"><input v-model="active" type="checkbox" :disabled="!session.can('employees.deactivate') || saving" />Сотрудник активен</label><button v-if="session.can('employees.update') || session.can('employees.deactivate')" class="button-primary align-start" :disabled="saving || !metadataDirty">Сохранить сведения</button></form></section>
      <EmployeeOrganization ref="organization" :employee-id="employee.id" :assignments="employee.org_assignments" @updated="updateOrganization" /></div>
    <EmployeeAccount v-if="session.can('users.view') || session.can('users.create') || session.can('users.deactivate')" ref="account" :employee-id="employee.id" />
    <div class="section-heading subsection"><div><h3>Специальности и обучение</h3><p class="muted compact">Обучение по одной специальности не отменяет полученную квалификацию по другой.</p></div><button v-if="session.can('specialties.training.manage')" :disabled="saving" @click="addingSpecialty = !addingSpecialty">Добавить специальность</button></div>
    <div class="table-scroll"><table><thead><tr><th>Специальность</th><th>Состояние</th><th>Известные даты</th><th>Основание</th><th>Действие</th></tr></thead><tbody><tr v-for="specialty in employee.specialties" :key="specialty.id"><td><strong>{{ specialty.specialty.code }}</strong><small>{{ specialty.specialty.name }}</small></td><td><span class="badge" :class="specialty.status === 'qualified' ? 'badge-green' : 'badge-amber'">{{ specialty.status === 'qualified' ? 'Квалификация получена' : specialty.status === 'training' ? 'Обучение' : 'Не подтверждено' }}</span><small v-if="specialty.status !== 'qualified'">Не допускает назначения</small></td><td><small>Обучение: {{ specialty.training_started_at ?? 'не указано' }}</small><small>Получена: {{ specialty.qualified_at ?? 'не указано' }}</small><small>Срок: {{ specialty.valid_until ?? 'не указан' }}</small></td><td>{{ specialty.basis || 'Не указано' }}</td><td><button v-if="specialty.status !== 'qualified' && session.can('specialties.qualify')" :data-qualify="specialty.id" :disabled="saving" @click="startQualify(specialty)">Подтвердить квалификацию</button><span v-else class="muted">—</span></td></tr><tr v-if="!employee.specialties.length"><td colspan="5" class="state">Специальности пока не внесены.</td></tr></tbody></table></div>
    <form v-if="addingSpecialty" class="inset-form form-grid" @submit.prevent="addSpecialty"><h4>Новая специальность</h4><ApiMessage :error="refsError" /><div class="form-columns"><label>Специальность<select v-model="specialtyId" required><option value="">Выберите из справочника</option><option v-for="item in specialties.filter(s => s.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Состояние<select v-model="status"><option value="training">Обучение</option><option value="unknown_legacy">Исторические сведения, не подтверждены</option></select></label><label>Начало обучения, если известно<input v-model="started" type="date" /></label><label>Окончание срока, если известно<input v-model="validUntil" type="date" /></label></div><label>Основание<textarea v-model="basis" rows="2" /></label><p class="muted compact">Получение квалификации подтверждается отдельным действием уполномоченного сотрудника.</p><button class="button-primary align-start" :disabled="saving || !specialtyId">Сохранить специальность</button></form>
    <form v-if="qualifying" data-confirm-qualification class="inset-form form-grid" @submit.prevent="qualify">
      <h4>Подтверждение квалификации {{ qualifying.specialty.code }}</h4>
      <p class="muted compact">Если дата неизвестна, оставьте поле пустым: система сохранит её неизвестной. Явное подтверждение с основанием допускает назначение по специальности при выполнении остальных условий.</p>
      <div class="form-columns"><label>Дата получения, если известна<input v-model="qualifiedAt" name="qualified_at" type="date" /></label><label>Срок действия, если известен<input v-model="qualificationValidUntil" name="qualification_valid_until" type="date" /><small>Сохранённый срок можно уточнить или явно очистить по подтверждённым сведениям.</small></label><label>Основание<input v-model="qualificationBasis" name="qualification_basis" required /></label></div>
      <div class="button-row"><button class="button-primary" :disabled="saving || !qualificationBasis.trim()">Подтвердить получение</button><button type="button" :disabled="saving" @click="qualifying = null">Отмена</button></div>
    </form>
    <EmployeeAccess v-if="session.can('access.roles.view') || session.can('access.roles.assign') || session.can('access.effective.view')" ref="access" :employee-id="employee.id" />
  </section>
</template>
