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
function changeSource(value: string) {
  if (props.busy || value === source.value || (value === 'new' && (!session.can('documents.upload') || !props.kindOptions.length))) return
  if (source.value === 'new' && documentForm.value?.dirty && !window.confirm('Есть несохранённый новый документ. Перейти к выбору существующего?')) return
  source.value = value
}
defineExpose({ persist, dirty, newDocument })
</script>
<template>
  <fieldset class="form-grid" :disabled="busy"><legend>{{ heading || 'Документ приложения' }}</legend>
    <template v-if="source === 'existing'"><div class="document-actions"><label class="grow">Поиск по названию документа<input v-model="search" name="document_search" type="search" @keydown.enter.prevent="load()" /></label><button data-find-issue-documents type="button" :disabled="loading" @click="load()">Найти</button><button v-if="session.can('documents.upload') && kindOptions.length" data-document-new type="button" @click="changeSource('new')">+ Добавить новый</button></div><ApiMessage :error="error" /><p v-if="loading" class="state">Поиск документов…</p><label>Сохранённый документ<select v-model="selected" name="document_id" :required="required"><option value="">{{ required ? 'Выберите документ' : 'Без документа' }}</option><option v-if="selected && !list.results.some(item => item.id === selected)" :value="selected">{{ shownDocument && !('restricted' in shownDocument) ? shownDocument.title || 'Выбранный документ' : 'Сохранённый документ (доступ ограничен)' }}</option><option v-for="item in list.results" :key="item.id" :value="item.id">{{ item.title || 'Без названия' }} · {{ item.source_kind === 'paper_original' ? 'Бумажный оригинал' : 'Копия' }} · {{ item.versions.length ? `Версий: ${item.versions.length}` : 'Без электронного файла' }}</option></select></label><PaginationBar :page="currentPage" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading || Boolean(busy)" @change="load" /><BasisPreview v-if="shownDocument" :document="shownDocument" heading="Выбранный документ" /></template>
    <template v-else><button data-document-existing type="button" @click="changeSource('existing')">Выбрать сохранённый</button><BasisDocumentForm ref="documentForm" :department-id="departmentId" :busy="busy" :input-locked="!session.can('documents.upload')" :heading="heading || 'Документ приложения'" :kind-options="kindOptions" saved-note="Состав комплекта и факт выдачи сохраняются отдельно." @changed="emit('changed')" /></template>
  </fieldset>
</template>

<style scoped>
.document-actions{display:flex;align-items:end;gap:10px;flex-wrap:wrap}.grow{flex:1;min-width:180px}.document-actions button{flex-shrink:0}
</style>
