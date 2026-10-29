<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { WorkIssueStatus } from '../../api/issuance'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
const props = defineProps<{ expertiseId: string; materialId: string }>()
const api = useApi(), session = useSessionStore(), requests = new LatestRequest(), value = ref<WorkIssueStatus | null>(null), loading = ref(false), error = ref<unknown>(null)
const enabled = computed(() => session.issuanceEnabled && session.can('expertise.view'))
async function load() {
  if (!enabled.value) return
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<WorkIssueStatus>(`/expertises/${props.expertiseId}/issue-status/`, { signal }), result => { value.value = result; loading.value = false }) } catch (cause) { error.value = cause; loading.value = false }
}
watch([() => props.expertiseId, enabled], () => { requests.cancel(); value.value = null; if (enabled.value) void load() }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <section v-if="enabled" data-expertise-issue-status class="card stack-card">
    <div class="section-heading"><h2>Выдача материалов</h2><div class="button-row">
      <button :disabled="loading" @click="load">Обновить факт выдачи</button>
      <RouterLink v-if="value?.package && !value.package.restricted && session.can('issue.view')" :to="`/issue-packages/${value.package.id}`">Комплект материала</RouterLink>
      <RouterLink v-else-if="value?.status === 'not_issued' && !value.package?.restricted && session.can('issue.view') && session.can('issue.prepare')" data-open-material-package :to="{ path: '/issue-packages/new', query: { material_id: materialId } }">Подготовить комплект материала</RouterLink>
    </div></div>
    <ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка факта выдачи…</p>
    <template v-else-if="value"><p v-if="value.status === 'issued'" class="message message-success">{{ value.fact_origin === 'historical' ? 'Историческая отметка выдачи' : 'Материалы выданы' }}: {{ value.issued_on || 'Дата неизвестна' }}</p><p v-else-if="value.status === 'not_issued'" class="muted">{{ value.fact_origin === 'historical' ? 'Дата выдачи в журнале отсутствует; новый факт передачи не зафиксирован.' : 'Не выдано — серверный факт передачи не зафиксирован.' }}</p><p v-else class="muted">Сведения о выдаче недоступны.</p><p v-if="value.package?.restricted" class="muted compact">Доступ к полному комплекту ограничен.</p></template>
    <HelpTip label="Завершение и выдача">Завершение этой экспертизы не означает выдачу всего материала.</HelpTip>
  </section>
</template>
