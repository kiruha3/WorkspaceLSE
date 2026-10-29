<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import {orderingParams} from '../../shared/ui/tableSorting'
import {useRouteTableSort} from '../../shared/ui/useRouteTableSort'

import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import { emptyLetterOptions, letterStateLabels, type Letter, type LetterOptions } from '../../api/letters'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import LetterDraftForm from './LetterDraftForm.vue'
const {ordering,sortTable}=useRouteTableSort()
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter(), requests = new LatestRequest(), optionsRequests = new LatestRequest()
const enabled = computed(() => session.correspondenceEnabled && session.can('letters.view'))
const creating = computed(() => route.query.create === '1' && session.can('letters.draft') && (!route.query.parent_id || session.can('letters.reply')))
const keys = ['search', 'direction', 'state', 'kind_id', 'responsible_id', 'department_id', 'expertise_id', 'registered_from', 'registered_to', 'received_from', 'received_to', 'control_status'] as const
const filters = reactive(Object.fromEntries(keys.map(key => [key, String(route.query[key] ?? '')])) as Record<typeof keys[number], string>)
const options = ref<LetterOptions>(emptyLetterOptions()), list = ref<Page<Letter>>({ count: 0, next: null, previous: null, results: [] }), loading = ref(false), error = ref<unknown>(null), optionsError = ref<unknown>(null)
const currentPage = computed(() => Math.max(1, Number(route.query.page) || 1))
const parentId = computed(() => typeof route.query.parent_id === 'string' ? route.query.parent_id : undefined)
const expertiseId = computed(() => typeof route.query.expertise_id === 'string' ? route.query.expertise_id : undefined)
const initialDirection = computed(() => route.query.direction === 'outgoing' ? 'outgoing' : 'incoming')
async function load() {
  if (!enabled.value || creating.value) return
  loading.value = true; error.value = null
  const query = new URLSearchParams({...orderingParams(ordering.value), ...Object.fromEntries(keys.filter(key => route.query[key]).map(key => [key, String(route.query[key])])), page: String(currentPage.value) })
  try { await requests.run(signal => api.request<Page<Letter>>(`/letters/?${query}`, { signal }), value => { list.value = value; loading.value = false }) } catch (cause) { error.value = cause; loading.value = false }
}
async function loadOptions() { if (!enabled.value) return; try { await optionsRequests.run(signal => api.request<LetterOptions>('/letters/options/', { signal }), value => { options.value = value }) } catch (cause) { optionsError.value = cause } }
async function filter(nextPage = 1) { await router.replace({ path: '/letters', query: {...orderingParams(ordering.value), ...Object.fromEntries(keys.filter(key => filters[key]).map(key => [key, filters[key]])), page: String(nextPage) } }) }
async function created(value: Letter) { requests.cancel(); await router.push(`/letters/${value.id}`) }
watch([() => route.fullPath, enabled], () => { requests.cancel(); if (enabled.value && route.path === '/letters') { keys.forEach(key => { filters[key] = String(route.query[key] ?? '') }); void load(); void loadOptions() } }, { immediate: true })
onBeforeUnmount(() => { requests.cancel(); optionsRequests.cancel() })
</script>
<template>
  <p v-if="!enabled" class="state">Переписка недоступна в этой сессии.</p>
  <template v-else><div class="page-heading"><div><p class="eyebrow">Ручной учёт деловой переписки</p><h1>Журнал переписки</h1><p class="muted">Входящие, исходящие и отдельный контроль ответов.</p></div><RouterLink v-if="session.can('letters.draft') && !creating" :to="{ path: '/letters', query: { create: '1' } }" class="button-primary">Новое письмо</RouterLink><RouterLink v-if="creating" to="/letters">← К журналу</RouterLink></div><ApiMessage :error="optionsError" />
    <section v-if="creating" class="card"><LetterDraftForm :options="options" :initial-direction="initialDirection" :parent-id="parentId" :expertise-id="expertiseId" @updated="created" @cancel="router.push('/letters')" /></section>
    <section v-else class="card"><form class="toolbar work-filters" @submit.prevent="filter()"><label>Поиск<input v-model="filters.search" name="search" type="search" placeholder="Тема, номер, корреспондент" /></label><label>Направление<select v-model="filters.direction" name="direction"><option value="">Все</option><option value="incoming">Входящие</option><option value="outgoing">Исходящие</option></select></label><label>Состояние<select v-model="filters.state" name="state"><option value="">Все</option><option v-for="(label, state) in letterStateLabels" :key="state" :value="state">{{ label }}</option></select></label><label>Вид<select v-model="filters.kind_id" name="kind_id"><option value="">Все</option><option v-for="item in options.kinds" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Ответственный<select v-model="filters.responsible_id" name="responsible_id"><option value="">Все доступные</option><option v-for="item in options.employees" :key="item.id" :value="item.id">{{ item.full_name }}</option></select></label><label>Отдел<select v-model="filters.department_id" name="department_id"><option value="">Все доступные</option><option v-for="item in options.departments" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>Контроль<select v-model="filters.control_status" name="control_status"><option value="">Все</option><option value="open">Открыт</option><option value="closed">Закрыт</option><option value="overdue">Просрочен</option></select></label><label>Регистрация с<input v-model="filters.registered_from" name="registered_from" type="date" /></label><label>Регистрация по<input v-model="filters.registered_to" name="registered_to" type="date" /></label><label>Получено с<input v-model="filters.received_from" name="received_from" type="date" /></label><label>Получено по<input v-model="filters.received_to" name="received_to" type="date" /></label><button :disabled="loading">Применить</button></form><p v-if="filters.expertise_id" class="muted compact">Переписка выбранной работы <button type="button" @click="filters.expertise_id = ''; filter()">Снять фильтр работы</button></p><ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка переписки…</p><div v-else class="table-scroll"><SortableTable :rows="list.results" :columns='[{"key": "number", "label": "Номер / тема"}, {"key": "direction", "label": "Направление / вид"}, {"key": "registered_on", "label": "Регистрация / получение"}, {"key": "responsible", "label": "Ответственный"}, {"key": "state", "label": "Отправка"}, {"key": "control", "label": "Контроль"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}"><tr v-for="item in tableRows" :key="item.id"><td><RouterLink data-open-letter :to="{ path: `/letters/${item.id}`, query: { return: route.fullPath } }"><strong>{{ item.registration?.registration_number || 'Без внутреннего номера' }}</strong><small>{{ item.content.subject || 'Без темы' }}</small></RouterLink></td><td>{{ item.direction === 'incoming' ? 'Входящее' : 'Исходящее' }}<small>{{ item.content.kind?.name || 'Вид не указан' }}</small></td><td>{{ item.registration?.registered_on || 'Не зарегистрировано' }}<small>Получено: {{ item.received_on || 'Неизвестно' }}</small></td><td>{{ item.responsible?.full_name || 'Не указан' }}</td><td>{{ letterStateLabels[item.state] }}</td><td>{{ item.control ? item.control.status === 'open' ? 'Открыт' : 'Закрыт' : item.allowed_actions.includes('control.view') ? 'Не поставлено' : 'Недоступно' }}<small v-if="item.control">{{ item.control.due_on || 'Срок неизвестен' }}{{ item.control.overdue ? ' · Просрочен' : '' }}</small></td></tr><tr v-if="!list.results.length"><td colspan="6" class="state">Писем по этой выборке нет.</td></tr></SortableTable></div><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="filter" /></section>
  </template>
</template>
