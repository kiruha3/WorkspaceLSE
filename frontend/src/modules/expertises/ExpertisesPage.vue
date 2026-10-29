<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import {orderingParams} from '../../shared/ui/tableSorting'
import {useRouteTableSort} from '../../shared/ui/useRouteTableSort'

import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { Expertise, Page, Reference } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import JournalSyncActions from '../imports/JournalSyncActions.vue'
import { useSessionStore } from '../../stores/session'
const {ordering,sortTable}=useRouteTableSort()
const api = useApi(), route = useRoute(), router = useRouter(), session = useSessionStore(), requests = new LatestRequest(), optionsRequests = new LatestRequest(), downloads = new LatestRequest()
const filterKeys = ['search', 'department_id', 'specialty_id', 'employee_id', 'received_from', 'received_to', 'state', 'calendar_days_min', 'calendar_days_max'] as const
const filters = reactive(Object.fromEntries(filterKeys.map(key => [key, String(route.query[key] ?? '')])) as Record<typeof filterKeys[number], string>)
const list = ref<Page<Expertise>>({ count: 0, next: null, previous: null, results: [] }), loading = ref(false), error = ref<unknown>(null), refsError = ref<unknown>(null)
const downloading = ref(false), downloadError = ref<unknown>(null)
const canExport = computed(() => session.can('expertise.view') && session.can('expertise.export'))
const departments = ref<Reference[]>([]), specialties = ref<Reference[]>([]), employees = ref<{ id: string; full_name: string }[]>([])
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const stateLabels = { in_progress: 'В производстве', suspended: 'Приостановлена', completed: 'Завершена', without_execution: 'Без исполнения' }
async function load() {
  loading.value = true; error.value = null
  const query = new URLSearchParams({...orderingParams(ordering.value), ...Object.fromEntries(filterKeys.filter(key => route.query[key]).map(key => [key, String(route.query[key])])), page: String(page.value) })
  try { await requests.run(signal => api.request<Page<Expertise>>(`/expertises/?${query}`, { signal }), result => { list.value = result; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function filter(nextPage = 1) { await router.replace({ path: '/expertises', query: {...orderingParams(ordering.value), ...Object.fromEntries(filterKeys.filter(key => filters[key]).map(key => [key, filters[key]])), page: String(nextPage) } }) }
async function download() {
  if (downloading.value || !canExport.value) return
  downloading.value = true; downloadError.value = null
  const query = new URLSearchParams(Object.fromEntries(filterKeys.filter(key => route.query[key]).map(key => [key, String(route.query[key])])))
  if(ordering.value)query.set('ordering',ordering.value)
  try {
    await downloads.run(signal => api.download(`/expertises/export.xlsx?${query}`, signal, 'expertises.xlsx'), file => {
      const url = URL.createObjectURL(file.blob), link = document.createElement('a')
      link.href = url; link.download = file.filename; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      downloading.value = false
    })
  } catch (cause) { downloadError.value = cause; downloading.value = false }
}
async function loadOptions() {
  try {
    await optionsRequests.run(async signal => {
      const [departments, specialties, options] = await Promise.all([api.allPages<Reference>('/references/departments/', signal), api.allPages<Reference>('/references/specialties/', signal), api.request<{ employees: { id: string; full_name: string }[] }>('/expertises/filter-options/', { signal })])
      return { departments, specialties, employees: options.employees }
    }, value => { departments.value = value.departments; specialties.value = value.specialties; employees.value = value.employees })
  } catch (cause) { refsError.value = cause }
}
watch(() => route.fullPath, () => { downloads.cancel(); downloading.value = false; downloadError.value = null; if (route.path === '/expertises') { filterKeys.forEach(key => { filters[key] = String(route.query[key] ?? '') }); void load() } })
onMounted(() => { void load(); void loadOptions() })
onBeforeUnmount(() => { requests.cancel(); optionsRequests.cancel(); downloads.cancel() })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Разрешённая область работ</p><h1>Реестр экспертиз</h1><p class="muted">Номер, специальность и текущий состав исполнителей. Перепоручение сохраняет историю.</p></div><div v-if="canExport" class="export-actions"><button data-export-expertises :disabled="loading || downloading" @click="download">{{ downloading ? 'Подготовка Excel…' : 'Скачать Excel' }}</button><small class="muted">Вся выборка по применённым фильтрам</small></div></div>
  <ApiMessage :error="downloadError" />
  <JournalSyncActions/>
  <section class="card">
    <form class="toolbar work-filters" @submit.prevent="filter()">
      <label class="search-field">Поиск<input v-model="filters.search" name="search" type="search" placeholder="Номер или материал" /></label>
      <label>Отдел<select v-model="filters.department_id" name="department_id"><option value="">Все доступные</option><option v-for="item in departments" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label>
      <label>Специальность<select v-model="filters.specialty_id" name="specialty_id"><option value="">Все доступные</option><option v-for="item in specialties" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label>
      <label>Текущий исполнитель<select v-model="filters.employee_id" name="employee_id"><option value="">Все доступные</option><option v-for="item in employees" :key="item.id" :value="item.id">{{ item.full_name }}</option></select></label>
      <label>Поступило с<input v-model="filters.received_from" name="received_from" type="date" /></label><label>По дату<input v-model="filters.received_to" name="received_to" type="date" /></label>
      <label>Состояние<select v-model="filters.state" name="state"><option value="">Все состояния</option><option v-for="(label, value) in stateLabels" :key="value" :value="value">{{ label }}</option></select></label>
      <label>Календарные дни — от<input :value="filters.calendar_days_min" name="calendar_days_min" type="number" min="0" max="365000" step="1" @input="filters.calendar_days_min = ($event.target as HTMLInputElement).value" /></label>
      <label>Календарные дни — до<input :value="filters.calendar_days_max" name="calendar_days_max" type="number" min="0" max="365000" step="1" @input="filters.calendar_days_max = ($event.target as HTMLInputElement).value" /></label>
      <button :disabled="loading">Применить</button>
    </form>
    <ApiMessage :error="refsError" /><ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка экспертиз…</p>
    <div v-else class="table-scroll"><SortableTable :rows="list.results" :columns='[{"key": "registration_number", "label": "Номер / материал"}, {"key": "received_at", "label": "Поступление"}, {"key": "department", "label": "Отдел / специальность"}, {"key": "executors", "label": "Текущие исполнители"}, {"key": "composition", "label": "Характер / состав"}, {"key": "state", "label": "Состояние"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}">
      <tr v-for="item in tableRows" :key="item.id">
        <td><RouterLink data-open-expertise :to="{ path: `/expertises/${item.id}`, query: { return: route.fullPath } }"><strong>{{ item.registration_number }}</strong></RouterLink><small v-if="item.material.is_demo" class="badge badge-amber">Учебная запись</small><small>{{ item.material.title || 'Без названия' }}</small><small v-if="item.historical_number">Исторический: {{ item.historical_number }}</small><small v-if="item.origin_kind === 'historical'">Перенос журнала</small></td>
        <td>{{ item.receipt.received_at }}</td>
        <td>{{ item.department.code }} · {{ item.department.name }}<small>{{ item.specialty ? `${item.specialty.code} · ${item.specialty.name}` : 'Специальность не уточнена' }}</small></td>
        <td><p v-for="assignment in item.current_assignments" :key="assignment.id">{{ assignment.employee.full_name }}</p><template v-if="!item.current_assignments.length"><span class="badge badge-amber">Не назначен в новом учёте</span><small v-for="person in item.historical?.current_participants ?? []" :key="person.id">Историческая связь: {{ person.full_name }}</small></template></td>
        <td>{{ item.appointment_nature === 'primary' ? 'Первичная' : item.appointment_nature === 'repeated' ? 'Повторная' : item.appointment_nature === 'additional' ? 'Дополнительная' : 'Характер не уточнён' }}<small v-if="item.is_commission === null">Состав не уточнён</small><small v-else-if="item.is_commission">Комиссионная · один номер</small><small v-if="item.complex_group">Комплекс · {{ item.complex_group.title }}</small></td>
        <td><span class="badge" :class="item.state === 'in_progress' ? 'badge-green' : ''">{{ stateLabels[item.state] }}</span></td>
      </tr>
      <tr v-if="!list.results.length"><td colspan="6" class="state">Экспертиз по этой выборке нет.</td></tr>
    </SortableTable></div>
    <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="filter" />
  </section>
</template>
<style scoped>
.export-actions { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; flex-shrink: 0; }
@media (max-width: 720px) { .export-actions { align-items: flex-start; } }
</style>
