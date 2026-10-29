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
const addingSpecialty = ref(false), specialtyId = ref(''), status = ref(session.can('specialties.training.manage')?'training':'qualified'), started = ref(''), acquired = ref(''), basis = ref(''), validUntil = ref('')
const qualifying = ref<EmployeeSpecialty | null>(null), qualifiedAt = ref(''), qualificationBasis = ref(''), qualificationValidUntil = ref(''), qualificationStarted = ref(''), metadataEditing = ref(false), qualificationInitial = ref('')
const canAddSpecialty = computed(()=>session.canAny('specialties.training.manage','specialties.qualify'))
const canEditSpecialty = (specialty:EmployeeSpecialty)=>session.can(specialty.status==='qualified'?'specialties.qualify':'specialties.training.manage')
const canSaveSpecialty = computed(()=>qualifying.value&&(metadataEditing.value?canEditSpecialty(qualifying.value):session.can('specialties.qualify')))
const access = ref<InstanceType<typeof EmployeeAccess> | null>(null)
const account = ref<InstanceType<typeof EmployeeAccount> | null>(null)
const organization = ref<InstanceType<typeof EmployeeOrganization> | null>(null)
const metadataDirty = computed(() => fullName.value !== originalName.value || active.value !== originalActive.value)
const qualificationStamp = computed(()=>JSON.stringify([qualifiedAt.value,qualificationBasis.value,qualificationValidUntil.value,qualificationStarted.value]))
const qualificationDirty = computed(() => qualifying.value !== null && qualificationStamp.value !== qualificationInitial.value)
const dirty = computed(() => metadataDirty.value || (addingSpecialty.value && Boolean(specialtyId.value || started.value || acquired.value || basis.value || validUntil.value)) || qualificationDirty.value || Boolean(access.value?.dirty || account.value?.dirty || organization.value?.dirty))
const busy = computed(() => saving.value || Boolean(account.value?.busy || access.value?.busy || organization.value?.busy))
useDirtyGuard(() => dirty.value, inject(routerKey, undefined), () => busy.value)
defineExpose({ dirty, busy })
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
  if (saving.value || !session.can(status.value==='qualified'?'specialties.qualify':'specialties.training.manage')) return
  saving.value = true; error.value = null; success.value = ''
  try {
    await api.request(`/employees/${props.employee.id}/specialties/`, { method: 'POST', body: { specialty_id: specialtyId.value, status: status.value, training_started_at: started.value || null, qualified_at: status.value==='qualified'?acquired.value||null:null, valid_until: validUntil.value || null, basis: basis.value } })
    addingSpecialty.value = false; specialtyId.value = ''; started.value = ''; acquired.value = ''; validUntil.value = ''; basis.value = ''
    success.value = 'Специальность сохранена сервером.'
    await refresh()
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
async function loadSpecialtyOptions(){
  refsError.value=null
  try{specialties.value=await api.allPages<Reference>('/references/specialties/')}
  catch(cause){refsError.value=cause}
}
function toggleAddSpecialty(){
  addingSpecialty.value=!addingSpecialty.value
  if(addingSpecialty.value&&!specialties.value.length)void loadSpecialtyOptions()
}
function startQualify(specialty: EmployeeSpecialty, metadata=false) {
  if (qualificationDirty.value && !window.confirm('Заменить несохранённые сведения специальности?')) return
  metadataEditing.value=metadata;qualifying.value = specialty; qualifiedAt.value = specialty.qualified_at??''; qualificationBasis.value = specialty.basis; qualificationValidUntil.value = specialty.valid_until ?? ''; qualificationStarted.value=specialty.training_started_at??''; qualificationInitial.value=qualificationStamp.value; error.value = null; success.value = ''
}
async function qualify() {
  if (!qualifying.value || saving.value || !canSaveSpecialty.value) return
  saving.value = true; error.value = null; success.value = ''
  try {
    const specialty = await api.request<EmployeeSpecialty>(`/employee-specialties/${qualifying.value.id}/${metadataEditing.value?'':'qualify/'}`, { method: metadataEditing.value?'PATCH':'POST', body: { expected_version: qualifying.value.version, ...(metadataEditing.value?{training_started_at:qualificationStarted.value||null}:{}), qualified_at: qualifiedAt.value || null, ...(metadataEditing.value||qualificationValidUntil.value !== (qualifying.value.valid_until ?? '') ? {valid_until:qualificationValidUntil.value || null} : {}), basis: qualificationBasis.value.trim() } })
    emit('updated', { ...props.employee, specialties: props.employee.specialties.map(item => item.id === specialty.id ? specialty : item) })
    qualifying.value = null; qualifiedAt.value = ''; qualificationBasis.value = ''; success.value = 'Специальность сохранена сервером.'
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
  if (session.can('specialties.training.manage')) await loadSpecialtyOptions()
})
</script>

<template>
  <section class="card employee-card">
    <div class="section-heading"><div><p class="eyebrow">Карточка сотрудника · версия {{ employee.version }}</p><h2>{{ employee.full_name }}</h2></div><div class="button-row"><span v-if="dirty" class="badge badge-amber">Есть изменения</span><button :disabled="saving" @click="reload">Обновить карточку</button></div></div>
    <ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <div class="detail-columns"><section><h3>Общие сведения</h3><form class="form-grid" @submit.prevent="saveDetails"><label>ФИО<input v-model="fullName" required :disabled="!session.can('employees.update') || saving" /></label><label class="check-label"><input v-model="active" type="checkbox" :disabled="!session.can('employees.deactivate') || saving" />Сотрудник активен</label><button v-if="session.can('employees.update') || session.can('employees.deactivate')" class="button-primary align-start" :disabled="saving || !metadataDirty">Сохранить сведения</button></form></section>
      <EmployeeOrganization ref="organization" :employee-id="employee.id" :assignments="employee.org_assignments" @updated="updateOrganization" /></div>
    <EmployeeAccount v-if="session.canAny('users.view', 'users.create', 'users.reset_password', 'users.deactivate')" ref="account" :employee-id="employee.id" />
    <div class="section-heading subsection"><div><h3>Специальности и обучение</h3><p class="muted compact">Статус «Получена» не требует отдельного подтверждения. Даты и основание необязательны, хранятся для справки и не ограничивают назначение. Обучение по специальности назначения не допускает.</p></div><button v-if="canAddSpecialty" data-add-specialty :disabled="saving" @click="toggleAddSpecialty">Добавить специальность</button></div>
    <div class="table-scroll"><table><thead><tr><th>Специальность</th><th>Состояние</th><th>Даты · справочно</th><th>Основание · необязательно</th><th>Действия</th></tr></thead><tbody><tr v-for="specialty in employee.specialties" :key="specialty.id"><td><strong>{{ specialty.specialty.code }}</strong><small>{{ specialty.specialty.name }}</small></td><td><span class="badge" :class="specialty.status === 'qualified' ? 'badge-green' : 'badge-amber'">{{ specialty.status === 'qualified' ? 'Получена' : specialty.status === 'training' ? 'Обучение' : 'Исторические сведения' }}</span><small v-if="specialty.status !== 'qualified'">Не допускает назначения</small></td><td><small>Обучение: {{ specialty.training_started_at ?? 'не указано' }}</small><small>Получена: {{ specialty.qualified_at ?? 'не указано' }}</small><small>Срок: {{ specialty.valid_until ?? 'не указан' }}</small></td><td>{{ specialty.basis || 'Не указано' }}</td><td><div class="button-row"><button v-if="canEditSpecialty(specialty)" :data-edit-specialty="specialty.id" :disabled="saving" @click="startQualify(specialty,true)">Изменить сведения</button><button v-if="specialty.status !== 'qualified' && session.can('specialties.qualify')" :data-qualify="specialty.id" :disabled="saving" @click="startQualify(specialty)">Отметить полученной</button></div></td></tr><tr v-if="!employee.specialties.length"><td colspan="5" class="state">Специальности пока не внесены.</td></tr></tbody></table></div>
    <form v-if="addingSpecialty" data-specialty-create class="inset-form form-grid" @submit.prevent="addSpecialty"><h4>Новая специальность</h4><ApiMessage :error="refsError" /><button v-if="refsError" type="button" @click="loadSpecialtyOptions">Повторить загрузку специальностей</button><div class="form-columns"><label>Специальность<select v-model="specialtyId" name="specialty_id" required><option value="">Выберите из справочника</option><option v-for="item in specialties.filter(s => s.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Состояние<select v-model="status" name="specialty_status"><option v-if="session.can('specialties.training.manage')" value="training">Обучение</option><option v-if="session.can('specialties.training.manage')" value="unknown_legacy">Исторические сведения, статус не уточнён</option><option v-if="session.can('specialties.qualify')" value="qualified">Получена</option></select></label><label>Начало обучения · справочно<input v-model="started" name="specialty_training_started_at" type="date" /></label><label v-if="status==='qualified'">Дата получения · справочно<input v-model="acquired" name="specialty_qualified_at" type="date" /></label><label>Окончание срока · справочно<input v-model="validUntil" name="specialty_valid_until" type="date" /></label></div><label>Основание · необязательно<textarea v-model="basis" name="specialty_basis" rows="2" /></label><p class="muted compact">Даты можно оставить пустыми. Выбранный статус сохраняется сразу; отдельное подтверждение не требуется.</p><button class="button-primary align-start" :disabled="saving || !specialtyId || !!refsError">Сохранить специальность</button></form>
    <form v-if="qualifying" data-confirm-qualification :data-specialty-metadata="metadataEditing?'':undefined" class="inset-form form-grid" @submit.prevent="qualify">
      <h4>{{metadataEditing?'Сведения специальности':'Отметить полученной'}} {{ qualifying.specialty.code }}</h4>
      <p class="muted compact">Даты и основание можно оставить пустыми. Они хранятся для справки и не ограничивают назначение. {{metadataEditing?'Статус специальности не изменяется.':'Специальность будет сохранена со статусом «Получена».'}}</p>
      <div class="form-columns"><label v-if="metadataEditing">Начало обучения · справочно<input v-model="qualificationStarted" name="qualification_training_started_at" type="date" /></label><label>Дата получения · справочно<input v-model="qualifiedAt" name="qualified_at" type="date" /></label><label>Окончание срока · справочно<input v-model="qualificationValidUntil" name="qualification_valid_until" type="date" /></label><label>Основание · необязательно<input v-model="qualificationBasis" name="qualification_basis" /></label></div>
      <div class="button-row"><button class="button-primary" :disabled="saving || !canSaveSpecialty">Сохранить специальность</button><button type="button" :disabled="saving" @click="qualifying = null">Отмена</button></div>
    </form>
    <EmployeeAccess v-if="session.can('access.roles.view') || session.can('access.roles.assign') || session.can('access.effective.view')" ref="access" :employee-id="employee.id" />
  </section>
</template>
