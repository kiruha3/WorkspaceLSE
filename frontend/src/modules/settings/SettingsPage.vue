<script setup lang="ts">
import {computed} from 'vue'
import {RouterLink} from 'vue-router'
import {useSessionStore} from '../../stores/session'
import {institutionPermission} from '../../api/reportPlans'
import {canManageStorage} from '../../api/storage'
const session=useSessionStore()
const storage=computed(()=>canManageStorage(session.user))
const source=computed(()=>institutionPermission(session.user,'imports.source.manage')&&session.user?.supported_modules?.includes('journal_source_settings'))
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Управление учреждением</p><h1>Настройки</h1><p class="muted">Сотрудники, доступ, справочники, источники данных и документы. Каждый раздел доступен по правам роли.</p></div></div>
 <div class="settings-grid">
  <RouterLink v-if="session.can('employees.view')" data-setting="people" to="/people" class="card settings-tile"><span class="eyebrow">Сотрудники</span><h2>Сотрудники</h2><p>Карточки сотрудников, отделы, должности и специальности.</p><span>Открыть сотрудников →</span></RouterLink>
  <RouterLink v-if="storage" data-setting="storage" to="/settings/storage" class="card settings-tile"><span class="eyebrow">Документы</span><h2>Папки документов</h2><p>Корневая папка года и проверка доступа сервером. Только чтение файлов.</p><span>Открыть настройки →</span></RouterLink>
  <RouterLink v-if="source" data-setting="source" to="/imports/source-settings" class="card settings-tile"><span class="eyebrow">Импорт</span><h2>Google-таблица</h2><p>Ссылка на таблицу, лист и источник обновления журнала.</p><span>Настроить источник →</span></RouterLink>
  <RouterLink v-if="session.canAny('access.roles.view','access.roles.manage')" data-setting="roles" to="/roles" class="card settings-tile"><span class="eyebrow">Доступ</span><h2>Роли и права</h2><p>Настройка действий, областей доступа и полномочий ролей.</p><span>Открыть роли →</span></RouterLink>
  <RouterLink v-if="session.canAccessDirectory" data-setting="accounts" to="/access" class="card settings-tile"><span class="eyebrow">Пользователи</span><h2>Учётные записи</h2><p>Пользователи системы, назначение ролей и проверка доступа.</p><span>Открыть учётные записи →</span></RouterLink>
  <RouterLink v-if="session.canAny('references.view','references.manage')" data-setting="references" to="/references" class="card settings-tile"><span class="eyebrow">Общие данные</span><h2>Справочники</h2><p>Отделы, должности, специальности и другие значения для выбора.</p><span>Открыть справочники →</span></RouterLink>
 </div>
 <p v-if="!storage&&session.can('access.roles.manage')" class="message">Для управления папками включите в нужной роли право «Настраивать папки документов» с областью «Учреждение». Новое право не выдаётся автоматически.</p>
</template>
<style scoped>.settings-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:20px}.settings-tile{display:flex;flex-direction:column;gap:12px;color:inherit;text-decoration:none}.settings-tile h2{font-size:21px;margin:0}.settings-tile p{color:var(--muted,#6e7f72);line-height:1.6;flex:1}.settings-tile>span:last-child{color:var(--primary,#145b3e);font-weight:600}.settings-tile:hover{border-color:var(--primary,#145b3e)}</style>
