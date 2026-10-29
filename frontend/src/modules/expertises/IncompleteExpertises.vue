<script setup lang="ts">
import { onBeforeUnmount, ref, useId, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'

interface MissingWork { id: string; registration_number: string; state: string; missing: { code: string; message: string }[] }
const api = useApi(), session = useSessionStore(), route = useRoute(), requests = new LatestRequest()
const empty = (): Page<MissingWork> => ({ count: 0, next: null, previous: null, results: [] })
const value = ref(empty()), currentPage = ref(1), busy = ref(false), error = ref<unknown>(null)
const expanded = ref(true), detailsId = useId()
async function load(page = currentPage.value) {
  if (!session.can('expertise.view')) return
  currentPage.value = page; value.value = empty(); busy.value = true; error.value = null
  try {
    await requests.run(signal => api.request<Page<MissingWork>>(`/expertises/incomplete/?page=${page}`, { signal }), result => {
      if (!result || !Number.isInteger(result.count) || result.count < 0 || !Array.isArray(result.results) || result.results.some(item => !item || typeof item.id !== 'string' || typeof item.registration_number !== 'string' || !Array.isArray(item.missing) || item.missing.some(gap => !gap || typeof gap.code !== 'string' || typeof gap.message !== 'string'))) throw new ApiError(200, 'invalid_response', 'Сервер не вернул список незаполненных сведений.')
      value.value = result; busy.value = false
    })
  } catch (cause) { error.value = cause; busy.value = false }
}
watch([() => session.user?.id, () => JSON.stringify(session.user?.access['expertise.view'] ?? [])], () => {
  requests.cancel(); value.value = empty(); currentPage.value = 1; error.value = null; busy.value = false
  if (session.can('expertise.view')) void load(1)
}, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <section data-incomplete-expertises class="card stack-card incomplete-expertises">
    <div class="section-heading incomplete-heading">
      <div><p class="eyebrow">Нужно дополнить</p><div class="incomplete-title"><h2>Не заполнено</h2><span v-if="!busy && !error" data-incomplete-count class="badge badge-amber">Экспертиз: {{ value.count }}</span></div><p class="muted compact">По каждой доступной экспертизе. Эти напоминания не запрещают завершение работы.</p></div>
      <div class="button-row">
        <button type="button" data-refresh-incomplete :disabled="busy" @click="load()">{{ busy ? 'Обновление…' : 'Обновить список' }}</button>
        <button type="button" data-toggle-incomplete :aria-expanded="expanded" :aria-controls="detailsId" @click="expanded = !expanded">{{ expanded ? 'Свернуть список' : 'Развернуть список' }}</button>
      </div>
    </div>
    <ApiMessage :error="error" />
    <p v-if="busy" class="state" role="status">Проверка незаполненных сведений…</p>
    <div v-show="expanded" :id="detailsId" data-incomplete-details>
      <template v-if="!busy && !error">
      <article v-for="work in value.results" :key="work.id" :data-incomplete-work="work.id" class="assignment-line">
        <RouterLink :to="{ path: `/expertises/${work.id}`, query: { return: route.fullPath } }"><strong>{{ work.registration_number }}</strong> → Открыть карточку</RouterLink>
        <ul><li v-for="gap in work.missing" :key="gap.code">{{ gap.message }}</li></ul>
      </article>
      <p v-if="!value.results.length" class="muted">Нет незаполненных сведений по доступным экспертизам.</p>
      <PaginationBar v-if="value.count" :page="currentPage" :count="value.count" :next="Boolean(value.next)" :previous="Boolean(value.previous)" :busy="busy" @change="load" />
      </template>
    </div>
  </section>
</template>
<style scoped>.incomplete-expertises{margin-bottom:24px}.incomplete-heading{flex-wrap:wrap;margin-bottom:0}.incomplete-title{display:flex;align-items:center;flex-wrap:wrap;gap:10px}.incomplete-expertises h2{margin:0}.incomplete-expertises ul{margin:10px 0 0;padding-left:22px}.incomplete-expertises li{margin:5px 0}</style>
