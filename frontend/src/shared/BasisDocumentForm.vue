<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ApiError, useApi } from '../api/client'
import { newCommandKey } from '../api/commandKey'
import type { BasisDocument, DocumentKind, FileVersion } from '../api/types'
const props = defineProps<{ departmentId: string; busy?: boolean; heading?: string; savedNote?: string; kindOptions?: { value: DocumentKind; label: string }[] }>()
const emit = defineEmits<{ changed: [] }>()
const api = useApi()
const options = computed(() => props.kindOptions ?? [{ value: 'resolution' as const, label: 'Постановление' }, { value: 'decision' as const, label: 'Определение' }])
const kind = ref<DocumentKind>(options.value[0]!.value), title = ref(''), sourceKind = ref<'paper_original' | 'uploaded_copy'>('paper_original')
const file = ref<File | null>(null), prepared = ref<BasisDocument | null>(null), preparedPayload = ref(''), uploaded = ref<File | null>(null)
const uploadKey = ref('')
const metadataAttempt = ref<{ stamp: string; key: string } | null>(null)
watch(file, () => { uploadKey.value = '' }, { flush: 'sync' })
const payload = computed(() => ({ kind: kind.value, title: title.value.trim(), source_kind: sourceKind.value, department_id: props.departmentId || null }))
const dirty = computed(() => Boolean(title.value || file.value || prepared.value || kind.value !== options.value[0]!.value || sourceKind.value !== 'paper_original'))
watch([() => JSON.stringify(payload.value), file], () => emit('changed'), { flush: 'sync' })
function chooseFile(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] ?? null }
async function persist(): Promise<BasisDocument> {
  if (!title.value.trim()) throw new ApiError(400, 'validation_error', props.heading ? 'Укажите название документа.' : 'Укажите название документа-основания.', { title: ['Обязательное поле'] })
  if (sourceKind.value === 'uploaded_copy' && !file.value && !prepared.value?.versions.length) throw new ApiError(400, 'file_required', props.heading ? 'Выберите файл документа.' : 'Выберите файл копии основания.', { file: ['Файл ещё не сохранён'] })
  const stamp = JSON.stringify(payload.value)
  if (!prepared.value || stamp !== preparedPayload.value) {
    if (metadataAttempt.value?.stamp !== stamp) metadataAttempt.value = { stamp, key: newCommandKey() }
    prepared.value = await api.request<BasisDocument>('/documents/', { method: 'POST', body: payload.value, headers: { 'Idempotency-Key': metadataAttempt.value.key } })
    preparedPayload.value = stamp; uploaded.value = null; uploadKey.value = ''
  }
  if (file.value && uploaded.value !== file.value) {
    const body = new FormData()
    body.append('expected_version', String(prepared.value.version)); body.append('file', file.value)
    if (!uploadKey.value) uploadKey.value = newCommandKey()
    const version = await api.request<FileVersion>(`/documents/${prepared.value.id}/versions/`, { method: 'POST', body, headers: { 'Idempotency-Key': uploadKey.value } })
    prepared.value = { ...prepared.value, version: prepared.value.version + 1, versions: [...prepared.value.versions, version] }
    uploaded.value = file.value
  }
  return prepared.value
}
defineExpose({ persist, dirty })
</script>
<template>
  <fieldset class="form-grid" :disabled="busy">
    <h4 v-if="heading">{{ heading }}</h4>
    <div class="form-columns"><label>{{ heading ? 'Вид документа' : 'Вид основания' }}<select v-model="kind" name="document_kind"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select></label><label>{{ heading ? 'Источник документа' : 'Источник основания' }}<select v-model="sourceKind" name="source_kind"><option value="paper_original">Бумажный оригинал</option><option value="uploaded_copy">Загруженная копия / фото</option></select></label></div>
    <label>Название или известные реквизиты<input v-model="title" name="document_title" maxlength="500" required /></label>
    <p v-if="sourceKind === 'paper_original'" class="muted compact">Заявляется наличие бумажного оригинала. {{ heading ? 'Электронного файла может пока не быть.' : 'Скан можно добавить позднее в карточке поступления.' }}</p>
    <label v-else>Файл копии или фото<input name="basis_file" type="file" @change="chooseFile" /><small>{{ heading ? 'Копия подтвердит документ после успешного сохранения файла на сервере.' : 'Копия станет основанием после успешного сохранения файла на сервере.' }}</small></label>
    <p v-if="prepared" class="message message-success" role="status">Документ подготовлен: {{ prepared.id }}. {{ prepared.versions.length ? 'Файл сохранён.' : 'Электронного файла пока нет.' }} {{ savedNote || (heading ? 'Событие срока сохраняется отдельно.' : 'Поступление и номер экспертизы сохраняются отдельно.') }}</p>
  </fieldset>
</template>
