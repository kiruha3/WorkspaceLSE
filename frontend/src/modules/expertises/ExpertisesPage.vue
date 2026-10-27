<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { Expertise, Page, Reference } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
const api = useApi(), route = useRoute(), router = useRouter(), requests = new LatestRequest(), optionsRequests = new LatestRequest()
const filterKeys = ['search', 'department_id', 'specialty_id', 'employee_id', 'received_from', 'received_to', 'state', 'calendar_days_min', 'calendar_days_max'] as const
const filters = reactive(Object.fromEntries(filterKeys.map(key => [key, String(route.query[key] ?? '')])) as Record<typeof filterKeys[number], string>)
const list = ref<Page<Expertise>>({ count: 0, next: null, previous: null, results: [] }), loading = ref(false), error = ref<unknown>(null), refsError = ref<unknown>(null)
const departments = ref<Reference[]>([]), specialties = ref<Reference[]>([]), employees = ref<{ id: string; full_name: string }[]>([])
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const stateLabels = { in_progress: 'В производстве', suspended: 'Приостановлена', completed: 'Завершена', without_execution: 'Без исполнения' }
async function load() {
  loading.value = true; error.value = null
  const query = new URLSearchParams({ ...Object.fromEntries(filterKeys.filter(key => route.query[key]).map(key => [key, String(route.query[key])])), page: String(page.value) })
  try { await requests.run(signal => api.request<Page<Expertise>>(`/expertises/?${query}`, { signal }), result => { list.value = result; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function filter(nextPage = 1) { await router.replace({ path: '/expertises', query: { ...Object.fromEntries(filterKeys.filter(key => filters[key]).map(key => [key, filters[key]])), page: String(nextPage) } }) }
async function loadOptions() {
  try {
    await optionsRequests.run(async signal => {
      const [departments, specialties, options] = await Promise.all([api.allPages<Reference>('/references/departments/', signal), api.allPages<Reference>('/references/specialties/', signal), api.request<{ employees: { id: string; full_name: string }[] }>('/expertises/filter-options/', { signal })])
      return { departments, specialties, employees: options.employees }
    }, value => { departments.value = value.departments; specialties.value = value.specialties; employees.value = value.employees })
  } catch (cause) { refsError.value = cause }
}
watch(() => route.fullPath, () => { if (route.path === '/expertises') { filterKeys.forEach(key => { filters[key] = String(route.query[key] ?? '') }); void load() } })
onMounted(() => { void load(); void loadOptions() })
onBeforeUnmount(() => { requests.cancel(); optionsRequests.cancel() })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Разрешённая область работ</p><h1>Реестр экспертиз</h1><p class="muted">Номер, специальность и текущий состав исполнителей. Перепоручение сохраняет историю.</p></div></div>
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
    <div v-else class="table-scroll"><table><thead><tr><th>Номер / материал</th><th>Поступление</th><th>Отдел / специальность</th><th>Текущие исполнители</th><th>Характер / состав</th><th>Состояние</th></tr></thead><tbody><tr v-for="item in list.results" :key="item.id"><td><RouterLink data-open-expertise :to="{ path: `/expertises/${item.id}`, query: { return: route.fullPath } }"><strong>{{ item.registration_number }}</strong></RouterLink><small>{{ item.material.title || 'Без названия' }}</small><small v-if="item.historical_number">Исторический: {{ item.historical_number }}</small></td><td>{{ item.receipt.received_at }}</td><td>{{ item.department.code }} · {{ item.department.name }}<small>{{ item.specialty.code }} · {{ item.specialty.name }}</small></td><td><p v-for="assignment in item.current_assignments" :key="assignment.id">{{ assignment.employee.full_name }}</p><span v-if="!item.current_assignments.length" class="badge badge-amber">Не назначен</span></td><td>{{ item.appointment_nature === 'primary' ? 'Первичная' : item.appointment_nature === 'repeated' ? 'Повторная' : 'Дополнительная' }}<small v-if="item.is_commission">Комиссионная · один номер</small><small v-if="item.complex_group">Комплекс · {{ item.complex_group.title }}</small></td><td><span class="badge" :class="item.state === 'in_progress' ? 'badge-green' : ''">{{ stateLabels[item.state] }}</span></td></tr><tr v-if="!list.results.length"><td colspan="6" class="state">Экспертиз по этой выборке нет.</td></tr></tbody></table></div>
    <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="filter" />
  </section>
</template>
