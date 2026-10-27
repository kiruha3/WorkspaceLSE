<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useApi } from '../../api/client'
import type { EmployeeAccount } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'

const props = defineProps<{ employeeId: string }>()
const api = useApi(), session = useSessionStore()
const account = ref<EmployeeAccount | null>(null), loading = ref(true), saving = ref(false)
const username = ref(''), password = ref(''), reason = ref(''), nextState = ref<boolean | null>(null)
const error = ref<unknown>(null), loadError = ref<unknown>(null), success = ref('')
const controller = new AbortController()
const canLookup = computed(() => session.can('users.view') || session.can('users.create') || session.can('users.deactivate'))
const dirty = computed(() => Boolean(username.value || password.value || (nextState.value !== null && reason.value)))
defineExpose({ dirty })
async function create() {
  if (saving.value || !session.can('users.create')) return
  saving.value = true; error.value = null; success.value = ''
  try {
    account.value = await api.request<EmployeeAccount>(`/employees/${props.employeeId}/account/`, { method: 'POST', body: { username: username.value.trim(), password: password.value } })
    password.value = ''; username.value = ''; success.value = 'Персональная учётная запись создана. Роли назначаются отдельно.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
async function changeState() {
  if (saving.value || nextState.value === null || !session.can('users.deactivate')) return
  saving.value = true; error.value = null; success.value = ''
  try {
    account.value = await api.request<EmployeeAccount>(`/employees/${props.employeeId}/account/`, { method: 'PATCH', body: { is_active: nextState.value, reason: reason.value.trim() } })
    reason.value = ''; nextState.value = null; success.value = 'Состояние входа сохранено сервером.'
  } catch (cause) { error.value = cause } finally { saving.value = false }
}
function cancelState() {
  if (reason.value && !window.confirm('Отменить несохранённое изменение входа?')) return
  nextState.value = null; reason.value = ''
}
async function load() {
  loadError.value = null; loading.value = true
  try { if (canLookup.value) account.value = await api.request<EmployeeAccount | null>(`/employees/${props.employeeId}/account/`, { signal: controller.signal }) }
  catch (cause) { if (!controller.signal.aborted) loadError.value = cause }
  finally { loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { controller.abort(); password.value = '' })
</script>
<template>
  <section class="subsection"><div class="section-heading"><div><h3>Персональный вход</h3><p class="muted compact">Учётная запись, активность сотрудника и назначения ролей управляются отдельно.</p></div><button v-if="loadError && canLookup" @click="load">Повторить загрузку</button></div>
    <ApiMessage :error="loadError" /><ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <p v-if="loading" class="state">Проверка учётной записи…</p>
    <div v-else-if="account" class="account-summary"><div><strong>{{ account.username }}</strong><p><span class="badge" :class="account.is_active ? 'badge-green' : 'badge-amber'">{{ account.is_active ? 'Вход разрешён' : 'Вход заблокирован' }}</span></p></div><button v-if="session.can('users.deactivate')" data-toggle-account :disabled="saving" @click="nextState = !account.is_active; error = null; success = ''">{{ account.is_active ? 'Заблокировать вход' : 'Разрешить вход' }}</button></div>
    <p v-else-if="!loadError" class="muted compact">{{ canLookup ? 'У сотрудника нет учётной записи.' : 'Просмотр учётной записи недоступен.' }}</p>
    <form v-if="!loading && !account && !loadError && session.can('users.create')" data-create-account class="inset-form form-grid" @submit.prevent="create"><h4>Создать персональную учётную запись</h4><fieldset :disabled="saving"><div class="form-columns"><label>Уникальный логин<input v-model="username" name="new_username" autocomplete="off" required maxlength="150" /></label><label>Первоначальный пароль<input v-model="password" name="new_password" type="password" autocomplete="new-password" required /></label></div><p class="muted compact">Создаётся вход для этой карточки сотрудника. Права выдаются отдельным назначением ролей.</p><button class="button-primary" :disabled="saving || !username.trim() || !password">{{ saving ? 'Создание…' : 'Создать учётную запись' }}</button></fieldset></form>
    <form v-if="account && nextState !== null" data-account-state-form class="inset-form form-grid" @submit.prevent="changeState"><h4>{{ nextState ? 'Разрешить персональный вход' : 'Заблокировать персональный вход' }}</h4><label>Основание<textarea v-model="reason" name="account_state_reason" rows="2" required :disabled="saving" /></label><div class="button-row"><button class="button-primary" :disabled="saving || !reason.trim()">Подтвердить изменение</button><button type="button" :disabled="saving" @click="cancelState">Отмена</button></div></form>
  </section>
</template>
