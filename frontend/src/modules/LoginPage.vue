<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'
import ApiMessage from '../shared/ui/ApiMessage.vue'
const session = useSessionStore(), router = useRouter()
const username = ref(''), password = ref(''), busy = ref(false), error = ref<unknown>(null)
async function submit() {
  if (busy.value) return
  busy.value = true; error.value = null
  try { await session.login(username.value.trim(), password.value); password.value = ''; await router.replace('/workspace') }
  catch (cause) { error.value = cause }
  finally { busy.value = false }
}
</script>
<template>
  <main class="login-screen"><section class="login-intro"><div class="brand"><span class="brand-mark">ЛСЭ</span><span>ФГБУ Абаканская ЛСЭ<small>Автоматизированная информационная система</small></span></div><div class="login-statement"><p class="eyebrow">Единое рабочее пространство</p><h1>Работа учреждения.<br />В одном контексте.</h1><p>Персональный доступ к сведениям, сотрудникам и действиям в вашей области ответственности.</p></div><p class="login-footer">Федеральное бюджетное учреждение<br />Абаканская лаборатория судебной экспертизы</p></section>
    <section class="login-form-side"><div class="login-form-card"><p class="eyebrow">Добро пожаловать</p><h2>Персональный вход</h2><p class="muted">Используйте учётную запись, выданную администратором доступа.</p><ApiMessage :error="error" /><p v-if="session.error" class="message message-error" role="alert">{{ session.error }}</p><form class="form-grid" @submit.prevent="submit"><label>Логин<input v-model="username" name="username" autocomplete="username" required autofocus :disabled="busy" /></label><label>Пароль<input v-model="password" name="password" type="password" autocomplete="current-password" required :disabled="busy" /></label><button class="button-primary login-submit" :disabled="busy || !username.trim() || !password">{{ busy ? 'Проверка…' : 'Войти в систему →' }}</button></form><p class="login-help">Если нет учётной записи или забыт пароль, обратитесь к администратору доступа.</p></div><span class="login-version">АИС · первый рабочий срез</span></section></main>
</template>
