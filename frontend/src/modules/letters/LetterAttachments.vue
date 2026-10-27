<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError } from '../../api/client'
import type { Letter } from '../../api/letters'
import type { DocumentKind } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import { useLetterAttempt } from './useLetterAttempt'
const props = defineProps<{ letter: Letter }>()
const emit = defineEmits<{ updated: [letter: Letter] }>()
const session = useSessionStore(), editing = ref(false), source = ref('existing'), documentId = ref(''), reason = ref('')
const documentForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const stamp = computed(() => JSON.stringify([source.value, documentId.value.trim(), reason.value.trim()]))
const { attempt, busy, error, recovering, reset, execute } = useLetterAttempt(stamp)
const authorized = computed(() => props.letter.allowed_actions.includes('letters.attach'))
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && attempt.value?.body.expected_version !== props.letter.version)
const dirty = computed(() => editing.value && Boolean(documentId.value || reason.value || documentForm.value?.dirty || attempt.value))
const confirmLeave = useDirtyGuard(() => dirty.value || busy.value, inject(routerKey, undefined))
const kinds = [{ value: 'letter' as DocumentKind, label: 'Документ переписки' }]
function cancel() { if (!busy.value && confirmLeave()) { editing.value = false; reset() } }
async function save() {
  if ((!authorized.value && !recovering.value) || (!reason.value.trim() && !recovering.value)) return
  const result = await execute(`/letters/${props.letter.id}/attachments/`, async () => ({ expected_version: props.letter.version, reason: reason.value.trim(), document_id: source.value === 'new' ? (await documentForm.value!.persist()).id : documentId.value.trim() }))
  if (result) { editing.value = false; documentId.value = ''; reason.value = ''; emit('updated', result.letter) }
}
</script>
<template>
  <section data-attachments class="card stack-card"><div class="section-heading"><h2>Приложения к письму</h2><button v-if="authorized && !editing" data-start-attachment @click="editing = true">Прикрепить документ</button></div><p class="muted compact">Позднее приложение не изменяет снимки регистрации и прежних отправок.</p>
    <div v-for="item in letter.attachments" :key="item.id" class="assignment-line"><BasisPreview :document="item.document" heading="Приложение" empty-text="Документ не указан." /><p>{{ item.reason }}</p><small>{{ item.actor.full_name }} · {{ item.created_at }}</small></div><p v-if="!letter.attachments.length" class="muted">Приложений нет. Бумажный оригинал может учитываться без электронной копии.</p>
    <form v-if="editing" data-attach-letter class="inset-form form-grid" @submit.prevent="save"><ApiMessage :error="error" /><p v-if="recovering" class="message">Ответ не получен. Повтор использует исходные документ, версию и ключ.</p><p v-else-if="!authorized" class="message message-error">Прикрепление больше не разрешено. Данные сохранены в форме.</p><p v-if="conflict" class="message">Для новой попытки примените свежую версию. <button type="button" :disabled="busy || !authorized" @click="reset">Применить версию {{ letter.version }}</button></p>
      <fieldset class="form-grid" :disabled="busy || (!authorized && !recovering)"><label>Источник документа<select v-model="source" name="attachment_source"><option value="existing">Существующий документ</option><option v-if="session.can('documents.upload')" value="new">Подготовить новый документ / файл</option></select></label><label v-if="source === 'existing'">Идентификатор доступного документа<input v-model="documentId" name="attachment_document_id" required /></label><BasisDocumentForm v-if="source === 'new' && session.can('documents.upload')" ref="documentForm" heading="Приложение к письму" saved-note="Приложение к письму сохраняется отдельно." :department-id="letter.department?.id ?? ''" :busy="busy" :kind-options="kinds" @changed="reset" /><label>Причина прикрепления<textarea v-model="reason" name="attachment_reason" required /></label></fieldset><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="recovering" :disabled="busy || ((!authorized || !reason.trim() || (source === 'existing' && !documentId.trim())) && !recovering)">{{ busy ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : 'Прикрепить документ' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
    </form>
  </section>
</template>
