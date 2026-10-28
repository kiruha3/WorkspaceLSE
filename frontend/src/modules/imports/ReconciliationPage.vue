<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { ApplicationPayload, Classification, ImportApplication, ImportSelection, ReconciliationOptions, ReconciliationRow } from '../../api/imports'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import SelectionEditor from './SelectionEditor.vue'
import ApplicationResult from './ApplicationResult.vue'
type ReconciliationPageData = Page<ReconciliationRow> & { batch_id: string; summary: Record<Classification, number> }
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter()
const requests = new LatestRequest(), optionRequests = new LatestRequest()
const enabled = computed(() => session.journalApplicationEnabled && session.importPreviewEnabled && session.can('imports.results.view'))
const canEdit = computed(() => enabled.value && session.can('imports.reconcile')), canApply = computed(() => enabled.value && session.can('imports.apply'))
const rows = ref<ReconciliationPageData | null>(null), options = ref<ReconciliationOptions | null>(null), editing = ref<ReconciliationRow | null>(null)
const editor = ref<InstanceType<typeof SelectionEditor> | null>(null)
const loading = ref(false), error = ref<unknown>(null), optionsError = ref<unknown>(null), writeError = ref<unknown>(null)
const filters = reactive({ search: '', classification: '' }), page = computed(() => Math.max(1, Number(route.query.page) || 1))
const chosen = ref<Record<string, { row_id: string; expected_selection_version: number; number: string }>>({})
const reason = ref(''), busy = ref(false), uncertain = ref(false), result = ref<ImportApplication | null>(null)
const attempt = ref<{ body: ApplicationPayload; key: string; batchId: string } | null>(null)
let generation = 0
const labels: Record<Classification, string> = { new: 'Новая', unchanged: 'Совпадает', changed: 'Изменена', invalid: 'Нужна проверка' }
const sourcePath = computed(() => `/imports/${route.params.id}`)
const back = computed(() => typeof route.query.return === 'string' && (route.query.return === sourcePath.value || route.query.return.startsWith(sourcePath.value + '?')) ? route.query.return : sourcePath.value)
useDirtyGuard(() => Boolean(reason.value.trim() || busy.value || attempt.value), router)
watch(() => reason.value.trim(), () => { attempt.value = null; uncertain.value = false; writeError.value = null }, { flush: 'sync' })
async function load() {
  requests.cancel(); rows.value = null; editing.value = null
  if (!enabled.value) return
  loading.value = true; error.value = null
  const query = new URLSearchParams({ page: String(page.value), ...Object.fromEntries(['search', 'classification'].filter(key => route.query[key]).map(key => [key, String(route.query[key])])) })
  const id = String(route.params.id)
  try { await requests.run(signal => api.request<ReconciliationPageData>(`/imports/${id}/reconciliation/?${query}`, { signal }), value => { rows.value = value; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function loadOptions() {
  optionRequests.cancel()
  if (!canEdit.value) return
  optionsError.value = null
  try { await optionRequests.run(signal => api.request<ReconciliationOptions>('/imports/reconciliation-options/', { signal }), value => { options.value = value }) }
  catch (cause) { optionsError.value = cause }
}
function filter(nextPage = 1) { void router.replace({ path: route.path, query: { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), page: String(nextPage), ...(route.query.return ? { return: route.query.return } : {}) } }) }
function toggle(item: ReconciliationRow, selected: boolean) {
  if (busy.value || !canApply.value || !item.selection || item.classification !== 'new' || item.blockers.length) return
  if (selected) chosen.value[item.row.id] = { row_id: item.row.id, expected_selection_version: item.selection.version, number: String(item.row.facts.registration_number || item.row.raw.B) }
  else delete chosen.value[item.row.id]
  attempt.value = null; uncertain.value = false
}
function saved(value: ImportSelection) {
  if (editing.value?.row.id !== value.row_id) return
  editing.value.selection = value; delete chosen.value[value.row_id]; editing.value = null
}
function reload() { if (!editor.value || editor.value.confirmLeave()) void load() }
function edit(item: ReconciliationRow) { if (!editor.value || editor.value.confirmLeave()) editing.value = item }
async function apply() {
  if (busy.value || !enabled.value || (!canApply.value && !uncertain.value) || !reason.value.trim() || !Object.keys(chosen.value).length) return
  const current = generation
  busy.value = true; writeError.value = null
  try {
    if (!attempt.value) attempt.value = { batchId: String(route.params.id), key: newCommandKey(), body: { reason: reason.value.trim(), selections: Object.values(chosen.value).sort((a, b) => a.row_id.localeCompare(b.row_id)).map(({ row_id, expected_selection_version }) => ({ row_id, expected_selection_version })) } }
    const response = await api.request<{ event: { id: string }; application: ImportApplication }>(`/imports/${attempt.value.batchId}/apply/`, { method: 'POST', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
    if (current !== generation) return
    result.value = response.application; chosen.value = {}; reason.value = ''; attempt.value = null; uncertain.value = false; void load()
  } catch (cause) { if (current === generation) { writeError.value = cause; uncertain.value = !(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response' } }
  finally { if (current === generation) busy.value = false }
}
watch([() => route.params.id, enabled], () => { generation++; chosen.value = {}; reason.value = ''; attempt.value = null; result.value = null; busy.value = false; uncertain.value = false; writeError.value = null })
watch([() => route.fullPath, enabled], () => { filters.search = typeof route.query.search === 'string' ? route.query.search : ''; filters.classification = typeof route.query.classification === 'string' ? route.query.classification : ''; void load() }, { immediate: true })
watch(canEdit, () => { void loadOptions() }, { immediate: true })
onBeforeUnmount(() => { generation++; requests.cancel(); optionRequests.cancel() })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Подтверждённый перенос</p><h1>Сверка журнала</h1><p class="muted">Исходный снимок неизменяем. Рабочие записи создаются только отдельным подтверждённым пакетом.</p></div><RouterLink :to="back">← К снимку</RouterLink></div>
  <p v-if="!enabled" class="message">Сверка недоступна: нужна поддержка сервера и право чтения источника.</p>
  <template v-else>
    <ApplicationResult v-if="result" :application="result" />
    <section class="card stack-card">
      <div v-if="rows" data-reconciliation-summary class="button-row"><span class="badge">Новые: {{ rows.summary.new }}</span><span class="badge">Совпадают: {{ rows.summary.unchanged }}</span><span class="badge">Изменены: {{ rows.summary.changed }}</span><span class="badge badge-amber">Нужна проверка: {{ rows.summary.invalid }}</span></div>
      <form class="toolbar" @submit.prevent="filter()"><label>Поиск<input v-model="filters.search" name="search" type="search" /></label><label>Классификация<select v-model="filters.classification" name="classification"><option value="">Все строки</option><option v-for="(label, code) in labels" :key="code" :value="code">{{ label }}</option></select></label><button :disabled="loading || busy">Применить</button><button type="button" :disabled="loading || busy" @click="reload">Обновить сверку</button></form>
      <ApiMessage :error="error" /><ApiMessage :error="optionsError" /><p v-if="loading" class="state">Загрузка сверки…</p>
      <div v-else-if="rows" class="table-scroll"><table><thead><tr><th v-if="canApply">В пакет</th><th>Строка / номер</th><th>Классификация</th><th>Отдел / специальность</th><th>Исторический исполнитель</th><th>Сопоставление</th></tr></thead><tbody>
        <tr v-for="item in rows.results" :key="item.row.id">
          <td v-if="canApply"><input data-select-application-row type="checkbox" :aria-label="`Выбрать ${item.row.facts.registration_number || item.row.raw.B}`" :checked="Boolean(chosen[item.row.id])" :disabled="busy || !item.selection || item.classification !== 'new' || Boolean(item.blockers.length)" @change="toggle(item, ($event.target as HTMLInputElement).checked)" /></td>
          <td><strong>{{ item.row.facts.registration_number || item.row.raw.B }}</strong><small>Строка {{ item.row.source_row }}</small></td>
          <td>{{ labels[item.classification] }}<small v-for="blocker in item.blockers" :key="blocker.code">{{ blocker.message }}</small><small v-if="item.existing_work">Уже в реестре: {{ item.existing_work.registration_number }}. Новый снимок не переписывает работу.</small></td>
          <td>{{ item.suggested_department?.code || 'Отдел не сопоставлен' }} / {{ item.suggested_specialty?.code || 'Специальность не уточнена' }}</td>
          <td>{{ item.row.facts.executor_raw || 'В источнике не указан' }}</td>
          <td><span v-if="item.selection">Сохранено · версия {{ item.selection.version }}</span><span v-else>Не сохранено</span><button v-if="canEdit" data-edit-selection :disabled="busy || !options" @click="edit(item)">{{ item.selection ? 'Проверить выбор' : 'Сопоставить' }}</button></td>
        </tr><tr v-if="!rows.results.length"><td colspan="6" class="state">Строк по выбранным условиям нет.</td></tr>
      </tbody></table></div>
      <PaginationBar v-if="rows" :page="page" :count="rows.count" :next="Boolean(rows.next)" :previous="Boolean(rows.previous)" :busy="loading || busy" @change="filter" />
    </section>
    <SelectionEditor ref="editor" v-if="editing && options" :key="editing.row.id" :batch-id="String(route.params.id)" :item="editing" :options="options" :can-edit="canEdit" @saved="saved" @cancel="editing = null" />
    <section v-if="Object.keys(chosen).length" class="card stack-card">
      <h2>Подтвердить пакет · {{ Object.keys(chosen).length }}</h2><ul><li v-for="entry in chosen" :key="entry.row_id">{{ entry.number }} · сопоставление версии {{ entry.expected_selection_version }}</li></ul>
      <p class="muted compact">Применяются только перечисленные сохранённые сопоставления. Ошибка любой строки откатывает весь пакет. Документы, назначения и допуски этим действием не создаются.</p>
      <form data-application-form class="form-grid" @submit.prevent="apply"><ApiMessage :error="writeError" /><p v-if="uncertain" class="message">Ответ не получен. Повтор использует тот же пакет, версии и ключ.</p><label>Основание применения пакета<textarea v-model="reason" name="application_reason" required rows="2" :disabled="busy || (!canApply && !uncertain)" /></label><button data-apply-import class="button-primary align-start" :disabled="busy || (!canApply && !uncertain) || !reason.trim()">{{ busy ? 'Применение…' : uncertain ? 'Повторить ту же попытку' : 'Применить подтверждённый пакет' }}</button></form>
    </section>
  </template>
</template>
