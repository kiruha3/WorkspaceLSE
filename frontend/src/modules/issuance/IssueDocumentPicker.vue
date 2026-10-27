<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import type { IssueItemKind } from '../../api/issuance'
import type { BasisDocument, DocumentKind, DocumentLink, Page } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
const props = defineProps<{ packageId: string; kind: IssueItemKind; departmentId: string; kindOptions: { value: DocumentKind; label: string }[]; document?: DocumentLink; required?: boolean; busy?: boolean; heading?: string }>()
const emit = defineEmits<{ changed: [] }>()
const api = useApi(), session = useSessionStore(), requests = new LatestRequest()
const source = ref('existing'), selected = ref(props.document?.id ?? ''), search = ref(''), loading = ref(false), error = ref<unknown>(null), currentPage = ref(1)
const list = ref<Page<BasisDocument>>({ count: 0, next: null, previous: null, results: [] }), documentForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const shownDocument = computed(() => list.value.results.find(item => item.id === selected.value) ?? (props.document?.id === selected.value ? props.document : null))
const dirty = computed(() => selected.value !== (props.document?.id ?? '') || source.value === 'new' || Boolean(documentForm.value?.dirty))
watch([selected, source], () => emit('changed'), { flush: 'sync' })
async function load(page = 1) {
  loading.value = true; error.value = null; currentPage.value = page
  const query = new URLSearchParams({ kind: props.kind, search: search.value.trim(), page: String(page) })
  try { await requests.run(signal => api.request<Page<BasisDocument>>(`/issue-packages/${props.packageId}/document-options/?${query}`, { signal }), value => { list.value = value; loading.value = false }) } catch (cause) { error.value = cause; loading.value = false }
}
async function persist(): Promise<string | null> {
  if (source.value === 'new') {
    if (!session.can('documents.upload') || !documentForm.value) throw new ApiError(403, 'forbidden', 'Подготовка нового документа больше не разрешена.')
    return (await documentForm.value.persist()).id
  }
  if (!selected.value && props.required) throw new ApiError(400, 'document_required', 'Выберите документ приложения.')
  return selected.value || null
}
watch(() => props.kind, () => { void load() }, { immediate: true })
onBeforeUnmount(() => requests.cancel())
const newDocument = computed(() => source.value === 'new')
defineExpose({ persist, dirty, newDocument })
</script>
<template>
  <fieldset class="form-grid" :disabled="busy"><legend>{{ heading || 'Документ приложения' }}</legend><label>Источник документа<select v-model="source" name="document_source"><option value="existing">Выбрать существующий</option><option v-if="session.can('documents.upload') && kindOptions.length" value="new">Подготовить новый документ / файл</option></select></label>
    <template v-if="source === 'existing'"><div class="button-row"><label>Поиск доступных документов<input v-model="search" name="document_search" type="search" /></label><button data-find-issue-documents type="button" :disabled="loading" @click="load()">Найти документы</button></div><ApiMessage :error="error" /><p v-if="loading" class="state">Поиск документов…</p><label>Документ<select v-model="selected" name="document_id" :required="required"><option value="">{{ required ? 'Выберите документ' : 'Без документа' }}</option><option v-if="selected && !list.results.some(item => item.id === selected)" :value="selected">{{ shownDocument && !('restricted' in shownDocument) ? shownDocument.title || 'Выбранный документ' : 'Сохранённый документ (доступ ограничен)' }}</option><option v-for="item in list.results" :key="item.id" :value="item.id">{{ item.title || 'Без названия' }} · {{ item.source_kind === 'paper_original' ? 'Бумажный оригинал' : 'Копия' }} · {{ item.versions.length ? `Версий: ${item.versions.length}` : 'Без электронного файла' }}</option></select></label><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading || Boolean(busy)" @change="load" /><BasisPreview v-if="shownDocument" :document="shownDocument" heading="Выбранный документ" /></template>
    <BasisDocumentForm v-else-if="session.can('documents.upload')" ref="documentForm" :department-id="departmentId" :busy="busy" :heading="heading || 'Документ приложения'" :kind-options="kindOptions" saved-note="Состав комплекта и факт выдачи сохраняются отдельно." @changed="emit('changed')" />
  </fieldset>
</template>
