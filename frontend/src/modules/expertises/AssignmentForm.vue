<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { AssignmentCandidate, Expertise } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const props = defineProps<{ expertise: Expertise; action: 'assign' | 'reassign' }>()
const emit = defineEmits<{ updated: [expertise: Expertise]; cancel: [] }>()
const api = useApi(), candidates = ref<AssignmentCandidate[]>([]), loading = ref(false), error = ref<unknown>(null), saving = ref(false)
const selected = ref<string[]>(props.expertise.current_assignments.map(item => item.employee.id)), reason = ref(''), initial = JSON.stringify(selected.value), requests = new LatestRequest()
const authorized = computed(() => props.expertise.allowed_actions.includes(`expertise.${props.action}`))
const dirty = computed(() => Boolean(reason.value) || JSON.stringify(selected.value) !== initial)
const confirmLeave = useDirtyGuard(() => dirty.value || saving.value, inject(routerKey, undefined))
const valid = computed(() => authorized.value && reason.value.trim() && (props.expertise.is_commission ? selected.value.length >= 2 : selected.value.length === 1) && selected.value.every(id => candidates.value.some(item => item.id === id && item.eligible)))
defineExpose({ dirty })
async function load() {
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<AssignmentCandidate[]>(`/expertises/${props.expertise.id}/assignment-candidates/`, { signal }), value => { candidates.value = value; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function save() {
  if (!valid.value || saving.value) return
  saving.value = true; error.value = null
  try {
    const value = await api.request<Expertise>(`/expertises/${props.expertise.id}/${props.action === 'assign' ? 'assignments' : 'reassign'}/`, { method: 'POST', body: { expected_version: props.expertise.version, employee_ids: selected.value, reason: reason.value.trim() } })
    reason.value = ''; selected.value = JSON.parse(initial) as string[]; emit('updated', value)
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function cancel() { if (!saving.value && confirmLeave()) emit('cancel') }
watch(() => props.expertise.id, load)
onMounted(load)
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <form class="inset-form form-grid" @submit.prevent="save"><div class="section-heading"><h3>{{ action === 'assign' ? 'Назначение экспертов' : 'Перепоручение работы' }}</h3><button type="button" :disabled="saving || loading" @click="load">Обновить допуски</button></div><ApiMessage :error="error" /><p v-if="!authorized" class="message message-error">Для этой работы действие больше не разрешено. Обновите карточку.</p><p class="muted compact">{{ expertise.is_commission ? 'Комиссия: выберите не менее двух участников под одним номером.' : 'Выберите одного эксперта по специальности работы.' }} Сервер повторно проверяет квалификацию и действительность назначения.</p><p v-if="loading" class="state">Загрузка кандидатов…</p><fieldset :disabled="saving || !authorized" class="candidate-list"><label v-for="candidate in candidates" :key="candidate.id" class="check-label candidate"><input v-model="selected" type="checkbox" :value="candidate.id" :disabled="!candidate.eligible && !selected.includes(candidate.id)" /><span><strong>{{ candidate.full_name }}</strong><small class="block" :class="{ 'candidate-denied': !candidate.eligible }">{{ candidate.message }}</small></span></label><p v-if="!loading && !candidates.length" class="muted compact">Нет доступных кандидатов в разрешённой области.</p></fieldset><label>Основание назначения / перепоручения<textarea v-model="reason" name="assignment_reason" required rows="2" :disabled="saving || !authorized" /></label><div class="button-row"><button type="submit" class="button-primary" :disabled="saving || loading || !valid">{{ saving ? 'Сохранение…' : action === 'assign' ? 'Назначить состав' : 'Сохранить перепоручение' }}</button><button type="button" :disabled="saving" @click="cancel">Отмена</button></div><p v-if="action === 'reassign'" class="muted compact">Номер сохраняется. Прежние назначения остаются в истории; неизменившиеся участники комиссии сохраняют свои назначения.</p></form>
</template>
