<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import { letterStateLabels, replyLabels, type LetterSummary } from '../../api/letters'
import type { Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
const props = defineProps<{ expertiseId: string }>()
const api = useApi(), session = useSessionStore(), requests = new LatestRequest(), loading = ref(false), error = ref<unknown>(null), currentPage = ref(1)
const list = ref<Page<LetterSummary>>({ count: 0, next: null, previous: null, results: [] })
const enabled = computed(() => session.correspondenceEnabled && session.can('letters.view'))
async function load(page = 1) {
  if (!enabled.value) return
  loading.value = true; error.value = null; currentPage.value = page
  try { await requests.run(signal => api.request<Page<LetterSummary>>(`/expertises/${props.expertiseId}/letters/?page=${page}`, { signal }), value => { list.value = value; loading.value = false }) } catch (cause) { error.value = cause; loading.value = false }
}
watch([() => props.expertiseId, enabled], () => { requests.cancel(); list.value = { count: 0, next: null, previous: null, results: [] }; void load() }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <section v-if="enabled" class="card stack-card" data-expertise-letters><div class="section-heading"><h2>Переписка по работе</h2><div class="button-row"><RouterLink :to="{ path: '/letters', query: { expertise_id: expertiseId } }">Журнал по работе</RouterLink><RouterLink v-if="session.can('letters.draft')" data-new-work-letter :to="{ path: '/letters', query: { create: '1', expertise_id: expertiseId } }">Новое письмо по работе</RouterLink></div></div><ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка переписки…</p><p v-for="item in list.results" :key="item.id"><RouterLink :to="{ path: `/letters/${item.id}`, query: { return: `/letters?expertise_id=${encodeURIComponent(expertiseId)}` } }">{{ item.registration_number || 'Без номера' }} · {{ item.subject || 'Без темы' }}</RouterLink> · {{ item.direction === 'incoming' ? 'Входящее' : 'Исходящее' }} · {{ letterStateLabels[item.state] }} <span v-if="item.reply_completeness">· {{ replyLabels[item.reply_completeness] }} ответ</span></p><p v-if="!loading && !list.results.length" class="muted">Доступных писем по работе нет.</p><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="load" /></section>
</template>
