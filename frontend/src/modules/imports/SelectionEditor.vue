<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { ImportSelection, ReconciliationOptions, ReconciliationRow, SelectionPayload } from '../../api/imports'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
const props = defineProps<{ batchId: string; item: ReconciliationRow; options: ReconciliationOptions; canEdit: boolean }>()
const emit = defineEmits<{ saved: [value: ImportSelection]; cancel: [] }>(), api = useApi()
const initial = props.item.selection??props.item.update_preview?.previous_selection
const departmentOptions = computed(() => props.options.departments.filter(ref => !props.item.row.facts.department_code || ref.code === props.item.row.facts.department_code))
const department = ref(initial?.department_id ?? props.item.suggested_department?.id ?? '')
const specialty = ref(props.item.selection?.specialty_id??props.item.suggested_specialty?.id??'')
const executorChanged=props.item.update_preview?.changes.some(change=>change.field==='executor_raw')
const employees = ref([...(props.item.selection?.employee_ids??(executorChanged?[]:initial?.employee_ids)??[])]), nature = ref<'' | NonNullable<SelectionPayload['appointment_nature']>>(initial?.appointment_nature ?? '')
const commission = ref(initial?.is_commission === null || initial?.is_commission === undefined ? '' : initial.is_commission ? 'yes' : 'no')
const complex = ref(initial?.complex_known ? initial.complex_group_key ? 'group' : 'no' : '')
const groupKey = ref(initial?.complex_group_key ?? ''), statistics = ref(initial?.statistics_confirmed ?? false), reason = ref(props.item.selection?.reason ?? '')
const busy = ref(false), saved = ref(false), error = ref<unknown>(null), uncertain = ref(false)
const attempt = ref<{ key: string; body: SelectionPayload } | null>(null)
let active = true
const fields = computed(() => JSON.stringify([department.value, specialty.value, employees.value, nature.value, commission.value, complex.value, groupKey.value.trim(), statistics.value, reason.value.trim()]))
const original = fields.value
const confirmLeave = useDirtyGuard(() => !saved.value && (fields.value !== original || busy.value || Boolean(attempt.value)), inject(routerKey, undefined))
const valid = computed(() => Boolean(department.value && reason.value.trim() && (props.canEdit || uncertain.value) && (uncertain.value || complex.value !== 'group' || groupKey.value.trim())))
watch(fields, () => { attempt.value = null; uncertain.value = false; error.value = null }, { flush: 'sync' })
async function submit() {
  if (busy.value || !valid.value) return
  busy.value = true; error.value = null
  try {
    if (!attempt.value) attempt.value = { key: newCommandKey(), body: {
      expected_version: props.item.selection?.version ?? 0, reason: reason.value.trim(), department_id: department.value,
      specialty_id: specialty.value || null, employee_ids: [...employees.value], appointment_nature: nature.value || null,
      is_commission: commission.value === '' ? null : commission.value === 'yes', complex_known: complex.value !== '',
      complex_group_key: complex.value === 'group' ? groupKey.value.trim() || null : null, statistics_confirmed: statistics.value,
    } }
    const result = await api.request<{ event: { id: string }; selection: ImportSelection }>(`/imports/${props.batchId}/rows/${props.item.row.id}/selection/`, { method: 'PUT', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
    if (active) { saved.value = true; emit('saved', result.selection) }
  } catch (cause) { if (active) { error.value = cause; uncertain.value = !(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response' } }
  finally { if (active) busy.value = false }
}
function cancel() { if (!busy.value && confirmLeave()) { saved.value = true; emit('cancel') } }
onBeforeUnmount(() => { active = false })
defineExpose({ confirmLeave })
</script>
<template>
  <section class="card stack-card">
    <div class="section-heading"><div><p class="eyebrow">Явный выбор ответственного</p><h2>Сопоставление {{ item.row.facts.registration_number || item.row.raw.B }}</h2></div><button :disabled="busy" @click="cancel">Закрыть</button></div>
    <p class="muted compact">Строка {{ item.row.source_row }} · в источнике: {{ item.row.facts.executor_raw || 'исполнитель не указан' }}. Сотрудник и допуск не создаются автоматически.</p>
    <p class="message">Фактический код отдела в номере: {{ item.row.facts.department_code || 'не распознан' }}. Старый отдел сохраняется, даже если сотрудник сейчас работает в другом. Номер и исходная строка не изменятся.</p>
    <form data-selection-form class="form-grid" @submit.prevent="submit">
      <ApiMessage :error="error" /><p v-if="uncertain" class="message">Ответ не получен. Повтор сохраняет исходные сведения, версию и ключ.</p><p v-if="!canEdit" class="message">Новое сопоставление больше не разрешено. Подготовленные сведения сохранены.</p>
      <fieldset class="form-grid" :disabled="busy || (!canEdit && !uncertain)">
        <div class="form-columns">
          <label>Фактический отдел экспертизы<select v-model="department" name="selection_department"><option value="">Выберите отдел</option><option v-for="ref in departmentOptions" :key="ref.id" :value="ref.id">{{ ref.code }} · {{ ref.name }}{{ ref.is_active ? '' : ' · неактивен, исторический' }}</option></select></label>
          <label>Специальность<select v-model="specialty" name="selection_specialty"><option value="">Неизвестна</option><option v-for="ref in options.specialties" :key="ref.id" :value="ref.id">{{ ref.code }} · {{ ref.name }}{{ ref.is_active ? '' : ' · неактивна, историческая' }}</option></select></label>
          <label>Характер назначения<select v-model="nature" name="selection_nature"><option value="">Не уточнён</option><option value="primary">Первичная</option><option value="repeated">Повторная</option><option value="additional">Дополнительная</option></select></label>
          <label>Состав<select v-model="commission" name="selection_commission"><option value="">Не уточнён</option><option value="no">Единоличная</option><option value="yes">Комиссионная — один номер</option></select></label>
          <label>Комплексность<select v-model="complex" name="selection_complex"><option value="">Не уточнена</option><option value="no">Не входит в комплекс</option><option value="group">Входит в явно указанную группу</option></select></label>
          <label v-if="complex === 'group'">Ключ комплекса внутри этого снимка<input v-model="groupKey" name="selection_group" required maxlength="100" /></label>
        </div>
        <fieldset class="candidate-list"><legend>Подтверждённые исторические участники</legend><label v-for="person in options.employees" :key="person.id" class="check-label"><input v-model="employees" type="checkbox" :value="person.id" />{{ person.full_name }}{{ person.is_active ? '' : ' · неактивен' }}</label></fieldset>
        <p class="muted compact">Q / R / S / T: {{ item.row.facts.questions ?? 'неизвестно' }} / {{ item.row.facts.categorical ?? 'неизвестно' }} / {{ item.row.facts.probable ?? 'неизвестно' }} / {{ item.row.facts.unresolved ?? 'неизвестно' }}.</p>
        <label class="check-label"><input v-model="statistics" name="selection_statistics" type="checkbox" />Подтверждаю полноту статистики вопросов</label><label>Основание сопоставления<textarea v-model="reason" name="selection_reason" required rows="2" /></label>
      </fieldset>
      <button class="button-primary align-start" :disabled="busy || !valid">{{ busy ? 'Сохранение…' : uncertain ? 'Повторить ту же попытку' : 'Сохранить сопоставление' }}</button>
      <p class="muted compact">Сохранение выбора ещё не переносит экспертизу. Фактический отдел и признанный код специальности сверяются сервером. Нынешний отдел сотрудника не меняется; пустое количество не становится нулём.</p>
    </form>
  </section>
</template>
