<script setup lang="ts">
import { useRoute, RouterLink } from 'vue-router'
import { useSessionStore } from '../stores/session'
import UiIcon from '../shared/ui/UiIcon.vue'
const session = useSessionStore(), route = useRoute()
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Персональное рабочее пространство</p><h1>Рабочее место</h1><p class="muted">{{ session.user?.employee?.full_name ?? session.user?.username }}, здесь доступны действия вашей учётной записи.</p></div><span class="badge badge-green">Персональная сессия</span></div>
  <p v-if="route.query.denied" class="message message-error" role="alert">Нет права на просмотр запрошенного раздела. Доступные разделы указаны в меню.</p>
  <section class="welcome-banner"><div><p class="eyebrow">АИС ФГБУ Абаканская ЛСЭ</p><h2>Сотрудники, квалификация<br />и доступ — в единой системе.</h2><p>Должность, роль и экспертная специальность учитываются отдельно. Один профиль поддерживает несколько направлений работы.</p></div><div class="banner-symbol"><UiIcon name="shield" /></div></section>
  <div class="home-grid"><section class="card"><div class="section-heading"><h2>Доступные разделы</h2><span class="subtle-label">По правам сессии</span></div>
    <RouterLink v-if="session.can('employees.view')" class="module-link" to="/people"><span class="module-icon"><UiIcon name="people" /></span><span><strong>Сотрудники</strong><small>Должности, специальности и обучение</small></span><UiIcon name="arrow" /></RouterLink>
    <RouterLink v-if="session.canAccessDirectory" class="module-link" to="/access"><span class="module-icon"><UiIcon name="shield" /></span><span><strong>Учётные записи</strong><small>Персональный вход и назначения ролей</small></span><UiIcon name="arrow" /></RouterLink>
    <RouterLink v-if="session.canAny('access.roles.view','access.roles.manage')" class="module-link" to="/roles"><span class="module-icon"><UiIcon name="shield" /></span><span><strong>Роли и права</strong><small>Настройка действий и областей доступа</small></span><UiIcon name="arrow" /></RouterLink>
    <p v-if="!session.can('employees.view') && !session.canAccessDirectory && !session.canAny('access.roles.view','access.roles.manage')" class="state">Для этой учётной записи пока не назначены разделы первого среза. Доступ назначает уполномоченный администратор.</p>
  </section><section class="card"><p class="eyebrow">Мой профиль</p><h2>{{ session.user?.employee?.full_name ?? 'Учётная запись' }}</h2><dl class="profile-facts"><div><dt>Логин</dt><dd>{{ session.user?.username }}</dd></div><div><dt>Связь с сотрудником</dt><dd>{{ session.user?.employee ? 'Установлена' : 'Не установлена' }}</dd></div><div><dt>Полномочия</dt><dd>По действующим назначениям ролей</dd></div></dl><p class="muted compact">Изменение роли применяется при следующем запросе. Роль не заменяет подтверждённую квалификацию.</p></section></div>
  <section class="card next-stage"><div><p class="eyebrow">Развитие системы</p><h2>Следом — рабочий путь экспертизы</h2><p class="muted">Приёмка, регистрация, назначения, документы и отчёт 15.1 будут подключены на следующих этапах. В текущем срезе операции и данные этих разделов ещё не созданы.</p></div><span class="badge">Следующий этап</span></section>
</template>
