<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
import { computed, inject, ref } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { Expertise, ExpertiseCommandResponse } from '../../api/types'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'

const props = defineProps<{ expertise: Expertise }>()
const emit = defineEmits<{ updated: [Expertise]; refresh: [] }>()
const api = useApi(), editing = ref(false), busy = ref(false), reason = ref(''), error = ref<unknown>(null)
const expectedVersion = ref(0), uncertain = ref(false)
const attempt = ref<{ key: string; body: { expected_version: number; reason: string } } | null>(null)
const authorized = computed(() => props.expertise.state === 'completed' && props.expertise.allowed_actions.includes('expertise.reopen'))
const history = computed(() => props.expertise.reopening_history ?? [])
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409)
const valid = computed(() => !busy.value && (uncertain.value ? Boolean(attempt.value) : authorized.value && Boolean(reason.value.trim()) && !conflict.value))
const confirmLeave = useDirtyGuard(() => editing.value && Boolean(reason.value.trim() || attempt.value), inject(routerKey, undefined), () => busy.value)
const date = (value: string | null) => value ? value.split('-').reverse().join('.') : 'Не указана'
const time = (value: string) => new Intl.DateTimeFormat('ru-RU', { timeZone: 'Asia/Krasnoyarsk', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))
function start() {
  if (!authorized.value) return
  editing.value = true; expectedVersion.value = props.expertise.version; reason.value = ''; error.value = null; attempt.value = null; uncertain.value = false
}
function cancel() { if (confirmLeave()) { editing.value = false; error.value = null; attempt.value = null; uncertain.value = false } }
function acceptVersion() {
  if (busy.value || !authorized.value || props.expertise.version === expectedVersion.value) return
  expectedVersion.value = props.expertise.version; attempt.value = null; error.value = null; uncertain.value = false
}
async function submit() {
  if (!valid.value) return
  busy.value = true; error.value = null
  if (!uncertain.value) attempt.value = { key: newCommandKey(), body: { expected_version: expectedVersion.value, reason: reason.value.trim() } }
  try {
    const response = await api.request<ExpertiseCommandResponse>(`/expertises/${props.expertise.id}/reopen/`, { method: 'POST', body: attempt.value!.body, headers: { 'Idempotency-Key': attempt.value!.key } })
    editing.value = false; reason.value = ''; attempt.value = null; uncertain.value = false
    if (response.expertise.version < props.expertise.version) emit('refresh')
    else emit('updated', response.expertise)
  } catch (cause) {
    error.value = cause
    uncertain.value = !(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response'
  } finally { busy.value = false }
}
</script>

<template>
  <section v-if="authorized || editing || history.length" class="card stack-card" data-reopen-panel>
    <div class="section-heading"><div><h2>Возврат в работу <HelpTip label="Возврат в работу">Прежние документы, исполнители и история завершения сохраняются.</HelpTip></h2></div><button v-if="authorized && !editing" type="button" data-reopen-start @click="start">Вернуть в работу</button></div>
    <form v-if="editing" data-reopen-form class="reopen-form" @submit.prevent="submit">
      <p class="message">Завершение будет отменено для текущего учёта и нового расчёта отчёта. Если осталась незакрытая приостановка, работа вернётся в состояние «Приостановлена»; иначе — «В работе». Согласование руководителем не требуется.</p>
      <HelpTip label="Историческая работа" v-if="expertise.historical && !expertise.historical.operational">Подтверждение основания для нового учёта и назначение эксперта выполняются отдельно. Этот возврат не создаёт их автоматически.</HelpTip>
      <label>Причина возврата<textarea v-model="reason" name="reopen_reason" rows="3" required :disabled="busy || uncertain" /></label>
      <ApiMessage :error="error" />
      <p v-if="uncertain" class="message">Результат запроса неизвестен. Повторите ту же команду: второй возврат не создастся.</p>
      <div v-if="conflict" class="message"><p>Данные изменились. Обновите серверные сведения, проверьте состояние и явно примите новую версию.</p><button type="button" :disabled="busy" @click="emit('refresh')">Обновить серверные сведения</button> <button v-if="expertise.version !== expectedVersion && authorized" data-reopen-use-version type="button" :disabled="busy" @click="acceptVersion">Использовать обновлённую версию {{ expertise.version }}</button></div>
      <p v-if="!authorized && !uncertain" class="message">Возврат больше недоступен для текущего состояния или прав. Причина сохранена в форме.</p>
      <div class="button-row"><button class="button-primary" data-reopen-confirm type="submit" :disabled="!valid">{{ busy ? 'Сохранение…' : uncertain ? 'Повторить ту же команду' : 'Подтвердить возврат в работу' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
    </form>
    <div v-if="history.length" data-reopening-history><h3>История возвратов</h3><article v-for="event in history" :key="event.id" class="reopening-event"><strong>{{ time(event.created_at) }} · {{ event.actor.full_name }}</strong><p>{{ event.reason }}</p><p class="muted compact">Возвращена: {{ event.restored_state === 'suspended' ? 'Приостановлена' : 'В работе' }}<template v-if="event.historical_completed_on"> · Прежняя дата окончания: {{ date(event.historical_completed_on) }}</template></p></article></div>
  </section>
</template>

<style scoped>
.reopen-form { display: grid; gap: 14px; margin-top: 16px; }
.reopen-form label { display: grid; gap: 8px; }
.reopen-form textarea { width: 100%; resize: vertical; }
.reopening-event { border-top: 1px solid var(--border); padding: 14px 0; }
</style>
