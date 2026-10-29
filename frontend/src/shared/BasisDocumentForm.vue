<script setup lang="ts">
import HelpTip from './ui/HelpTip.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ApiError, LatestRequest, useApi } from '../api/client'
import ApiMessage from './ui/ApiMessage.vue'
import { newCommandKey } from '../api/commandKey'
import type { BasisDocument, DocumentKind, FileVersion } from '../api/types'
const props = defineProps<{ departmentId: string; busy?: boolean; inputLocked?: boolean; heading?: string; savedNote?: string; requireFile?: boolean; kindOptions?: { value: DocumentKind; label: string }[]; allowExternalSource?: boolean; initialFile?: File }>()
const emit = defineEmits<{ changed: [] }>()
const api = useApi()
const options = computed(() => props.kindOptions ?? [{ value: 'resolution' as const, label: 'Постановление' }, { value: 'decision' as const, label: 'Определение' }])
const kind = ref<DocumentKind>(options.value[0]!.value), title = ref(props.initialFile?.name??''), sourceKind = ref<BasisDocument['source_kind']>(props.initialFile?'uploaded_copy':'paper_original'), sourceUrl=ref('')
const file = ref<File | null>(props.initialFile??null), prepared = ref<BasisDocument | null>(null), preparedPayload = ref(''), uploaded = ref<File | null>(null)
const uploadKey = ref('')
const uploadConflict=ref(false),currentDocument=ref<BasisDocument|null>(null),versionLoading=ref(false),versionError=ref<unknown>(null),versionRequests=new LatestRequest()
const conflictError=()=>new ApiError(409,'document_version_conflict','Изменилась версия подтверждающего документа. Сверьте актуальную версию ниже и явно примите её перед повторной загрузкой. Ввод и выбранный файл сохранены.')
const metadataAttempt = ref<{ stamp: string; key: string } | null>(null)
watch(file, () => { uploadKey.value = '' }, { flush: 'sync' })
const payload = computed(() => ({ kind: kind.value, title: title.value.trim(), source_kind: sourceKind.value, department_id: props.departmentId || null,...(sourceKind.value==='external_link'?{source_url:sourceUrl.value.trim()}:{}) }))
const dirty = computed(() => Boolean(title.value || file.value || prepared.value || kind.value !== options.value[0]!.value || sourceKind.value !== 'paper_original'))
watch([() => JSON.stringify(payload.value), file], () => emit('changed'), { flush: 'sync' })
watch(()=>JSON.stringify(payload.value),()=>{versionRequests.cancel();uploadConflict.value=false;currentDocument.value=null;versionLoading.value=false;versionError.value=null},{flush:'sync'})
function chooseFile(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] ?? null }
async function refreshDocumentVersion(){
 if(!prepared.value)return
 const id=prepared.value.id;versionLoading.value=true;versionError.value=null
 try{await versionRequests.run(signal=>api.request<BasisDocument>(`/documents/${id}/`,{signal}),value=>{if(prepared.value?.id===id)currentDocument.value=value;versionLoading.value=false})}
 catch(cause){versionError.value=cause;versionLoading.value=false}
}
function acceptDocumentVersion(){
 if(!currentDocument.value||currentDocument.value.id!==prepared.value?.id)return
 prepared.value=currentDocument.value;currentDocument.value=null;uploaded.value=null;uploadKey.value='';uploadConflict.value=false;versionError.value=null;emit('changed')
}
async function persist(): Promise<BasisDocument> {
  if(uploadConflict.value)throw conflictError()
  if (!title.value.trim()) throw new ApiError(400, 'validation_error', props.heading ? 'Укажите название документа.' : 'Укажите название документа-основания.', { title: ['Обязательное поле'] })
  if ((sourceKind.value === 'uploaded_copy' || props.requireFile) && !file.value && !prepared.value?.versions.length) throw new ApiError(400, 'file_required', props.heading ? 'Выберите файл документа.' : 'Выберите файл копии основания.', { file: ['Файл ещё не сохранён'] })
  const stamp = JSON.stringify(payload.value)
  if (!prepared.value || stamp !== preparedPayload.value) {
    if (metadataAttempt.value?.stamp !== stamp) metadataAttempt.value = { stamp, key: newCommandKey() }
    prepared.value = await api.request<BasisDocument>('/documents/', { method: 'POST', body: payload.value, headers: { 'Idempotency-Key': metadataAttempt.value.key } })
    preparedPayload.value = stamp; uploaded.value = null; uploadKey.value = ''
  }
  if (file.value && uploaded.value !== file.value) {
    const body = new FormData()
    body.append('expected_version', String(prepared.value.version)); body.append('file', file.value)
    if(file.value.webkitRelativePath)body.append('relative_path',file.value.webkitRelativePath)
    if (!uploadKey.value) uploadKey.value = newCommandKey()
    let version:FileVersion
    try{version = await api.request<FileVersion>(`/documents/${prepared.value.id}/versions/`, { method: 'POST', body, headers: { 'Idempotency-Key': uploadKey.value } })}
    catch(cause){if(cause instanceof ApiError&&cause.status===409){uploadConflict.value=true;currentDocument.value=null;throw conflictError()}throw cause}
    prepared.value = { ...prepared.value, version: prepared.value.version + 1, versions: [...prepared.value.versions, version] }
    uploaded.value = file.value
  }
  return prepared.value
}
onBeforeUnmount(()=>versionRequests.cancel())
defineExpose({ persist, dirty, uploadConflict })
</script>
<template>
  <fieldset class="form-grid" :disabled="busy">
    <h4 v-if="heading">{{ heading }}</h4>
    <fieldset class="form-grid" :disabled="inputLocked">
    <div class="form-columns"><label>{{ heading ? 'Вид документа' : 'Вид основания' }}<select v-model="kind" name="document_kind"><option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option></select></label><label>{{ heading ? 'Источник документа' : 'Источник основания' }}<select v-model="sourceKind" name="source_kind"><option value="paper_original">Бумажный оригинал</option><option value="uploaded_copy">Загруженная копия / фото</option><option v-if="allowExternalSource" value="external_link">Внешняя ссылка</option></select></label></div>
    <label v-if="sourceKind==='external_link'">Адрес источника<input v-model="sourceUrl" name="source_url" type="url" maxlength="2048" required/><HelpTip label="Внешняя ссылка">Ссылка сама по себе не подтверждает наличие принятого файла. Сохранённую копию можно загрузить отдельно.</HelpTip></label>
    <label>Название или известные реквизиты<input v-model="title" name="document_title" maxlength="500" required /></label>
    <HelpTip label="Бумажный оригинал" v-if="sourceKind === 'paper_original' && !requireFile">Заявляется наличие бумажного оригинала. {{ heading ? 'Электронного файла может пока не быть.' : 'Скан можно добавить позднее в карточке поступления.' }}</HelpTip>
    <label v-else>Файл копии или фото{{initialFile?` · выбран ${initialFile.webkitRelativePath||initialFile.name}`:''}}<input name="basis_file" type="file" :required="requireFile && !prepared?.versions.length" @change="chooseFile" /><HelpTip label="Загрузка файла">{{ heading ? 'Копия подтвердит документ после успешного сохранения файла на сервере.' : 'Копия станет основанием после успешного сохранения файла на сервере.' }}</HelpTip></label>
    </fieldset>
    <p v-if="prepared" class="message message-success" role="status">Документ подготовлен: {{ prepared.id }}. {{ prepared.versions.length ? 'Файл сохранён.' : 'Электронного файла пока нет.' }} {{ savedNote || (heading ? 'Событие срока сохраняется отдельно.' : 'Поступление и номер экспертизы сохраняются отдельно.') }}</p>
    <section v-if="uploadConflict" class="message" data-document-conflict>
      <p>Другой пользователь изменил документ. Карточку экспертизы обновлять не требуется. Сначала сверьте актуальные файлы; ваш выбранный файл не заменён.</p>
      <ApiMessage :error="versionError"/>
      <button data-refresh-document-version type="button" :disabled="busy||versionLoading" @click="refreshDocumentVersion">{{versionLoading?'Загрузка версии…':'Загрузить актуальную версию документа'}}</button>
      <template v-if="currentDocument"><p>Версия документа {{currentDocument.version}} · {{currentDocument.title}}</p><ul><li v-for="version in currentDocument.versions" :key="version.id">{{version.number}} · {{version.original_name}}</li></ul><button data-accept-document-version type="button" :disabled="busy||versionLoading" @click="acceptDocumentVersion">Принять версию {{currentDocument.version}} документа для повторной загрузки</button></template>
    </section>
  </fieldset>
</template>
