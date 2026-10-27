<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import { issueItemLabels, type IssueItemKind, type IssueOptions, type IssuePackage } from '../../api/issuance'
import type { DocumentLink, DocumentKind } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import IssueDocumentPicker from './IssueDocumentPicker.vue'
import { useIssueAttempt } from './useIssueAttempt'
const props = defineProps<{ package?: IssuePackage; materialId?: string; canPrepare?: boolean; options: IssueOptions }>()
const emit = defineEmits<{ updated: [value: IssuePackage]; cancel: [] }>()
const materials = ref(props.package?.content.materials_description ?? ''), note = ref(props.package?.content.note ?? ''), reason = ref(''), baseVersion = ref(props.package?.version), saved = ref(false), pickerChanges = ref(0)
type Row = { key: string; kind: IssueItemKind; expertise_id: string; document: DocumentLink; note: string }
const rows = ref<Row[]>(props.package?.content.items.map(item => ({ key: item.id, kind: item.kind, expertise_id: item.expertise_id, document: item.document, note: item.note })) ?? [])
const pickers = new Map<string, InstanceType<typeof IssueDocumentPicker>>()
const normalized = computed(() => ({ materials_description: materials.value.trim(), note: note.value.trim(), items: rows.value.map(item => ({ kind: item.kind, expertise_id: item.expertise_id, document_id: item.document?.id ?? null, note: item.note.trim() })) }))
const stamp = computed(() => JSON.stringify({ ...normalized.value, reason: reason.value.trim(), pickerChanges: pickerChanges.value }))
const initial = stamp.value
const { attempt, busy, error, recovering, reset, execute } = useIssueAttempt(stamp)
const authorized = computed(() => props.package ? props.package.allowed_actions.includes('issue.prepare') : Boolean(props.canPrepare))
const dirty = computed(() => !saved.value && (stamp.value !== initial || Boolean(attempt.value) || [...pickers.values()].some(item => item.dirty)))
const confirmLeave = useDirtyGuard(() => dirty.value || busy.value, inject(routerKey, undefined))
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && props.package && baseVersion.value !== props.package.version)
function bindPicker(key: string, value: unknown) { if (value) pickers.set(key, value as InstanceType<typeof IssueDocumentPicker>); else pickers.delete(key) }
function addItem() { if (props.options.item_kinds[0]) rows.value.push({ key: newCommandKey(), kind: props.options.item_kinds[0].code, expertise_id: '', document: null, note: '' }) }
function changed() { pickerChanges.value++ }
function acceptVersion() { baseVersion.value = props.package?.version; reset() }
function cancel() { if (!busy.value && confirmLeave()) { saved.value = true; emit('cancel') } }
function kinds(kind: IssueItemKind) { return (props.options.item_kinds.find(item => item.code === kind)?.document_kinds ?? []).map(value => ({ value: value as DocumentKind, label: issueItemLabels[value as IssueItemKind] || (value === 'letter' ? 'Документ переписки' : value) })) }
async function save() {
  if ((!authorized.value || !reason.value.trim()) && !recovering.value) return
  // Capture the revision and its version before document upload or another GET can finish.
  const source = { ...normalized.value, items: normalized.value.items.map(item => ({ ...item })), reason: reason.value.trim(), ...(props.package ? { expected_version: baseVersion.value } : {}) }
  const sourceRows = rows.value.map(item => ({ key: item.key, picker: pickers.get(item.key) }))
  const path = props.package ? `/issue-packages/${props.package.id}/draft/` : `/materials/${props.materialId}/issue-packages/`
  const response = await execute(path, async () => {
    for (let index = 0; index < source.items.length; index++) {
      if (!source.items[index]!.expertise_id) throw new ApiError(400, 'work_required', 'Выберите работу для каждого приложения.')
      source.items[index]!.document_id = await sourceRows[index]!.picker!.persist()
    }
    return source
  })
  if (response) { saved.value = true; emit('updated', response.package) }
}
</script>
<template>
  <form data-issue-package-draft class="form-grid" @submit.prevent="save"><div class="section-heading"><h2>{{ package ? 'Редакция состава комплекта' : 'Первоначальный комплект материала' }}</h2><span v-if="dirty" class="badge badge-amber">Есть изменения</span></div><ApiMessage :error="error" /><p v-if="recovering" class="message">Ответ не получен. Повтор использует прежние содержание, версию и ключ.</p><p v-else-if="!authorized" class="message message-error">Подготовка больше не разрешена. Ввод сохранён в форме.</p><p v-if="conflict" class="message">Серверный комплект изменился. Сравните его с сохранёнными полями формы. <button data-accept-package-version type="button" :disabled="busy || !authorized" @click="acceptVersion">Применить версию {{ package?.version }} к новой попытке</button></p>
    <fieldset class="form-grid" :disabled="busy || (!authorized && !recovering)"><label>Описание передаваемых материалов<textarea v-model="materials" name="materials_description" rows="4" /></label><label>Примечание к составу<textarea v-model="note" name="package_note" /></label>
      <template v-if="package"><h3>Дополнительные документы по работам</h3><div v-for="(item, index) in rows" :key="item.key" class="inset-form form-grid"><div class="form-columns"><label>Роль документа<select v-model="item.kind" :name="`item_kind_${index}`" @change="item.document = null"><option v-for="option in options.item_kinds" :key="option.code" :value="option.code">{{ option.name }}</option></select></label><label>Работа<select v-model="item.expertise_id" :name="`item_work_${index}`" required><option value="">Выберите работу</option><option v-for="work in package.works" :key="work.id" :value="work.id">{{ work.registration_number }} · {{ work.department.name }}</option></select></label></div><IssueDocumentPicker :key="`${item.key}-${item.kind}`" :ref="value => bindPicker(item.key, value)" :package-id="package.id" :kind="item.kind" :department-id="package.works.find(work => work.id === item.expertise_id)?.department.id ?? ''" :kind-options="kinds(item.kind)" :document="item.document" :busy="busy" required @changed="changed" /><label>Примечание к приложению<textarea v-model="item.note" :name="`item_note_${index}`" /></label><button type="button" @click="rows.splice(index, 1)">Убрать приложение</button></div><button data-add-package-item type="button" :disabled="!options.item_kinds.length" @click="addItem">Добавить документ по работе</button></template>
      <p v-else class="muted">Сохраните первоначальный черновик. Карточка покажет работы материала, требования и подбор документов.</p><label>Причина / основание редакции<textarea v-model="reason" name="package_reason" required /></label>
    </fieldset><p class="muted compact">Неполный черновик можно сохранить. Проверка и фактическая выдача — отдельные действия. Счёт не подтверждает оплату.</p><div class="button-row"><button type="submit" class="button-primary" :formnovalidate="recovering" :disabled="busy || ((!authorized || !reason.trim()) && !recovering)">{{ busy ? 'Сохранение…' : recovering ? 'Повторить ту же попытку' : 'Сохранить состав' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
  </form>
</template>
