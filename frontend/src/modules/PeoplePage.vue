<script setup lang="ts">
import SortableTable from '../shared/ui/SortableTable.vue'
import {orderingParams} from '../shared/ui/tableSorting'

import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { routerKey } from 'vue-router'
import { LatestRequest, useApi } from '../api/client'
import type { Employee, Page } from '../api/types'
import { useSessionStore } from '../stores/session'
import ApiMessage from '../shared/ui/ApiMessage.vue'
import PaginationBar from '../shared/ui/PaginationBar.vue'
import { useDirtyGuard } from '../shared/ui/useDirtyGuard'
import EmployeePanel from './people/EmployeePanel.vue'

const ordering=ref('')
function sortTable(value:string){ordering.value=value;void load(1)}
const api = useApi(), session = useSessionStore()
const list = ref<Page<Employee>>({ count: 0, next: null, previous: null, results: [] })
const search = ref(''), page = ref(1), loading = ref(false), loadingDetail = ref(false)
const error = ref<unknown>(null), detailError = ref<unknown>(null)
const selected = ref<Employee | null>(null), panel = ref<InstanceType<typeof EmployeePanel> | null>(null)
const mode = ref<'list' | 'detail' | 'create'>('list')
const creating = computed(() => mode.value === 'create')
const fullName = ref(''), saving = ref(false), createError = ref<unknown>(null), success = ref('')
const requests = new LatestRequest(), details = new LatestRequest()
const confirmLeave = useDirtyGuard(() => creating.value && Boolean(fullName.value), inject(routerKey, undefined))
async function load(nextPage = page.value) {
  page.value = nextPage; loading.value = true; error.value = null
  try { await requests.run(signal => api.request<Page<Employee>>(`/employees/?${new URLSearchParams({...orderingParams(ordering.value), search: search.value, page: String(page.value) })}`, { signal }), result => { list.value = result; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function open(employee: Employee) {
  if (!confirmLeave() || (panel.value?.dirty && !window.confirm('Есть несохранённые изменения карточки. Открыть другого сотрудника?'))) return
  mode.value = 'detail'; loadingDetail.value = true; detailError.value = null
  try { await details.run(signal => api.request<Employee>(`/employees/${employee.id}/`, { signal }), result => { selected.value = result; loadingDetail.value = false }) }
  catch (cause) { detailError.value = cause; loadingDetail.value = false }
}
function updated(employee: Employee) {
  selected.value = employee
  const index = list.value.results.findIndex(item => item.id === employee.id)
  if (index >= 0) list.value.results[index] = employee
}
function startCreate() {
  if (saving.value || panel.value?.busy || !confirmLeave() || (panel.value?.dirty && !window.confirm('Есть несохранённые изменения карточки. Открыть новую форму?'))) return
  details.cancel(); selected.value = null; loadingDetail.value = false; mode.value = 'create'; fullName.value = ''; createError.value = null; success.value = ''
}
function backToList() {
  if (saving.value || panel.value?.busy || !confirmLeave() || (panel.value?.dirty && !window.confirm('Есть несохранённые изменения карточки. Вернуться к списку?'))) return
  details.cancel(); mode.value = 'list'; selected.value = null; fullName.value = ''; loadingDetail.value = false; detailError.value = null; success.value = ''
}
async function create() {
  if (saving.value || !session.can('employees.create')) return
  saving.value = true; createError.value = null; success.value = ''
  try {
    const employee = await api.request<Employee>('/employees/', { method: 'POST', body: { full_name: fullName.value.trim() } })
    mode.value = 'detail'; fullName.value = ''; selected.value = employee; success.value = 'Сотрудник создан сервером.'
    await load()
  } catch (cause) { createError.value = cause }
  finally { saving.value = false }
}
onMounted(() => load())
onBeforeUnmount(() => { requests.cancel(); details.cancel() })
</script>

<template>
  <div class="page-heading"><div><p class="eyebrow">Кадровый учёт</p><h1>{{ mode === 'detail' ? selected?.full_name ?? 'Карточка сотрудника' : creating ? 'Новый сотрудник' : 'Сотрудники' }}</h1><p class="muted">Один человек — одна карточка, несколько должностей, специальностей и ролей.</p></div><div class="button-row"><button v-if="mode !== 'list'" data-back-to-people :disabled="saving||panel?.busy" @click="backToList">← Назад к списку</button><button v-if="!creating&&session.can('employees.create')" data-add-employee class="button-primary" :disabled="saving||panel?.busy" @click="startCreate">+ Добавить сотрудника</button></div></div>
  <section v-if="mode === 'list'" class="card">
    <form class="toolbar" @submit.prevent="load(1)"><label class="search-field">Поиск сотрудников<input v-model="search" type="search" placeholder="Фамилия, имя или отчество" /></label><button :disabled="loading">Найти</button><span class="toolbar-note">Данные в разрешённой области</span></form>
    <ApiMessage :error="error" /><p v-if="loading" class="state" aria-live="polite">Загрузка сотрудников…</p>
    <div v-else class="table-scroll"><SortableTable :rows="list.results" :columns='[{"key": "full_name", "label": "Сотрудник"}, {"key": "organization", "label": "Должности и подразделения"}, {"key": "specialties", "label": "Полученные специальности"}, {"key": "training", "label": "Обучение"}, {"key": "is_active", "label": "Состояние"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}">
      <tr v-for="employee in tableRows" :key="employee.id" data-employee-row :class="{ 'row-selected': employee.id === selected?.id }"><td><button class="text-button" :data-open-employee="employee.id" @click="open(employee)">{{ employee.full_name }}</button></td><td><p v-for="assignment in employee.org_assignments" :key="assignment.id" class="cell-line">{{ assignment.position.name }}<small>{{ assignment.department.name }}{{ assignment.valid_to ? ` · до ${assignment.valid_to}` : '' }}</small></p><span v-if="!employee.org_assignments.length" class="muted">Не указаны</span></td><td data-qualified><span v-for="specialty in employee.specialties.filter(s => s.status === 'qualified')" :key="specialty.id" class="badge badge-green" :title="specialty.specialty.name">{{ specialty.specialty.code }}</span><span v-if="!employee.specialties.some(s => s.status === 'qualified')" class="muted">Нет подтверждённых</span><small v-if="employee.specialties.some(s => s.status === 'unknown_legacy')">Есть неподтверждённые сведения</small></td><td data-training><span v-for="specialty in employee.specialties.filter(s => s.status === 'training')" :key="specialty.id" class="badge badge-amber" :title="specialty.specialty.name">{{ specialty.specialty.code }}</span><span v-if="!employee.specialties.some(s => s.status === 'training')" class="muted">Не ведётся</span></td><td><span class="badge" :class="employee.is_active ? 'badge-green' : ''">{{ employee.is_active ? 'Активен' : 'Неактивен' }}</span></td></tr>
      <tr v-if="!list.results.length"><td colspan="5" class="state">Сотрудников по этой выборке нет.</td></tr>
    </SortableTable></div>
    <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="load" />
  </section>
  <ApiMessage :error="detailError" /><p v-if="loadingDetail" class="state" aria-live="polite">Загрузка карточки…</p>
  <p v-if="success" class="message message-success" role="status">{{ success }}</p>
  <section v-if="creating" class="card narrow-card"><h2>Новый сотрудник</h2><p class="muted">Создание карточки не создаёт логин, роли или квалификацию.</p><ApiMessage :error="createError" /><form class="form-grid" @submit.prevent="create"><label>ФИО<input v-model="fullName" name="full_name" required maxlength="255" /></label><div class="button-row"><button class="button-primary" :disabled="saving || !fullName.trim()">{{ saving ? 'Сохранение…' : 'Создать карточку' }}</button><button type="button" :disabled="saving" @click="backToList">Отмена</button></div></form></section>
  <EmployeePanel v-if="mode === 'detail' && selected && !loadingDetail" :key="selected.id" ref="panel" :employee="selected" @updated="updated" />
</template>
