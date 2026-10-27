<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import { issueStateLabels, type IssuePackage } from '../../api/issuance'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter(), requests = new LatestRequest()
const enabled = computed(() => session.issuanceEnabled && session.can('issue.view'))
const keys = ['search', 'state', 'issued_from', 'issued_to'] as const
const filters = reactive(Object.fromEntries(keys.map(key => [key, String(route.query[key] ?? '')])) as Record<typeof keys[number], string>)
const list = ref<Page<IssuePackage>>({ count: 0, next: null, previous: null, results: [] }), loading = ref(false), error = ref<unknown>(null)
const currentPage = computed(() => Math.max(1, Number(route.query.page) || 1))
async function load() {
  if (!enabled.value) return
  loading.value = true; error.value = null
  const query = new URLSearchParams({ ...Object.fromEntries(keys.filter(key => route.query[key]).map(key => [key, String(route.query[key])])), page: String(currentPage.value) })
  try { await requests.run(signal => api.request<Page<IssuePackage>>(`/issue-packages/?${query}`, { signal }), value => { list.value = value; loading.value = false }) } catch (cause) { error.value = cause; loading.value = false }
}
async function filter(page = 1) { await router.replace({ path: '/issue-packages', query: { ...Object.fromEntries(keys.filter(key => filters[key]).map(key => [key, filters[key]])), page: String(page) } }) }
watch([() => route.fullPath, enabled], () => { requests.cancel(); if (enabled.value) { keys.forEach(key => { filters[key] = String(route.query[key] ?? '') }); void load() } }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <p v-if="!enabled" class="state">Выдача недоступна в этой сессии.</p><template v-else><div class="page-heading"><div><p class="eyebrow">Учёт полной передачи материалов</p><h1>Журнал выдачи</h1><p class="muted">Комплект всех работ материала, проверки и фактическая дата выдачи.</p></div></div><section class="card"><form class="toolbar work-filters" @submit.prevent="filter()"><label>Поиск<input v-model="filters.search" name="issue_search" type="search" placeholder="Материал или номер работы" /></label><label>Состояние<select v-model="filters.state" name="issue_state"><option value="">Все</option><option v-for="(label, state) in issueStateLabels" :key="state" :value="state">{{ label }}</option></select></label><label>Фактически выдано с<input v-model="filters.issued_from" name="issued_from" type="date" /></label><label>По дату<input v-model="filters.issued_to" name="issued_to" type="date" /></label><button :disabled="loading">Применить</button></form><ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка журнала выдачи…</p><div v-else class="table-scroll"><table><thead><tr><th>Материал</th><th>Работы</th><th>Состояние</th><th>Проверка состава</th><th>Фактическая выдача</th></tr></thead><tbody><tr v-for="item in list.results" :key="item.id"><td><RouterLink data-open-issue-package :to="{ path: `/issue-packages/${item.id}`, query: { return: route.fullPath } }"><strong>{{ item.material.title || 'Без названия' }}</strong></RouterLink><small>Редакция {{ item.content.number }}</small></td><td>{{ item.works.map(work => work.registration_number).join(', ') || 'Работ нет' }}</td><td>{{ issueStateLabels[item.state] }}</td><td>{{ item.readiness.check_current ? 'Действует' : 'Не выполнена или устарела' }}<small v-if="item.readiness.blockers.length">Есть недостающие части</small></td><td>{{ item.issuance?.issued_on || 'Не выдано' }}<small v-if="item.issuance">{{ item.issuance.method.name }} · {{ item.issuance.recipient_name }}</small></td></tr><tr v-if="!list.results.length"><td colspan="5" class="state">Комплектов по этой выборке нет.</td></tr></tbody></table></div><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="filter" /><p class="muted compact">Новый комплект открывается из блока выдачи в карточке экспертизы. Окончание работы само по себе не подтверждает выдачу.</p></section></template>
</template>
