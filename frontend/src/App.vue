<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useSessionStore } from './stores/session'
import UiIcon from './shared/ui/UiIcon.vue'
import ApiMessage from './shared/ui/ApiMessage.vue'
import { hasDirtyForms } from './shared/ui/useDirtyGuard'
const session = useSessionStore(), route = useRoute(), router = useRouter()
const logoutError = ref<unknown>(null), signingOut = ref(false), menuOpen = ref(false)
async function logout() {
  if (signingOut.value || (hasDirtyForms() && !window.confirm('Есть несохранённые изменения. Выйти из системы?'))) return
  signingOut.value = true; logoutError.value = null
  try { await session.logout(); await router.replace('/login') }
  catch (cause) { logoutError.value = cause }
  finally { signingOut.value = false }
}
watch(() => session.authenticated, value => { if (session.ready && !value && route.path !== '/login') void router.replace('/login') })
watch(() => route.path, () => { menuOpen.value = false })
</script>
<template>
  <RouterView v-if="route.path === '/login'" />
  <div v-else-if="session.authenticated" class="app-layout">
    <aside class="sidebar" :class="{ 'sidebar-open': menuOpen }"><RouterLink class="brand" to="/workspace"><span class="brand-mark">ЛСЭ</span><span>Абаканская ЛСЭ<small>ФГБУ · Минюст России</small></span></RouterLink><p class="sidebar-caption">Рабочее пространство</p><nav aria-label="Основное меню"><RouterLink to="/workspace"><UiIcon name="home" />Рабочее место</RouterLink><RouterLink v-if="session.can('employees.view')" to="/people"><UiIcon name="people" />Сотрудники</RouterLink><RouterLink v-if="session.can('access.roles.view')" to="/roles"><UiIcon name="shield" />Роли и права</RouterLink></nav><div class="sidebar-future"><p class="sidebar-caption">Следующие этапы</p><div><UiIcon name="folder" />Экспертизы<span>позже</span></div><div><UiIcon name="file" />Документы<span>позже</span></div><div><UiIcon name="chart" />Отчётность<span>позже</span></div></div><div class="sidebar-bottom"><span class="status-dot" /><span>Первый рабочий срез<small>Доступ · сотрудники · обучение</small></span></div></aside>
    <div class="workspace"><header class="topbar"><div class="topbar-context"><button class="mobile-menu" aria-label="Открыть меню" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">☰</button><span class="topbar-institution">ФГБУ Абаканская ЛСЭ</span><span class="topbar-divider">/</span><span>{{ route.meta.title }}</span></div><div class="account"><span class="avatar">{{ (session.user?.employee?.full_name ?? session.user?.username ?? '').charAt(0) }}</span><div><strong>{{ session.user?.employee?.full_name ?? session.user?.username }}</strong><small>{{ session.user?.username }}</small></div><button class="icon-button" :disabled="signingOut" aria-label="Выйти из системы" title="Выйти из системы" @click="logout"><UiIcon name="logout" /></button></div></header><main class="main-content"><ApiMessage :error="logoutError" /><RouterView /></main><footer class="workspace-footer">ФГБУ Абаканская ЛСЭ<span>Персональная сессия · права проверяются сервером</span></footer></div>
  </div>
  <main v-else class="state full-state">Проверка персональной сессии…</main>
</template>
