<script setup lang="ts">
import {computed} from 'vue'
import {RouterLink} from 'vue-router'
import {useSessionStore} from '../../stores/session'
import {institutionPermission} from '../../api/reportPlans'
import {canManageStorage} from '../../api/storage'
import UiIcon from '../../shared/ui/UiIcon.vue'
const session=useSessionStore()
const storage=computed(()=>canManageStorage(session.user))
const source=computed(()=>institutionPermission(session.user,'imports.source.manage')&&session.user?.supported_modules?.includes('journal_source_settings'))
const groups=computed(()=>[
 {id:'team',title:'Команда и доступ',items:[
  {id:'people',to:'/people',icon:'people',title:'Сотрудники',description:'Отделы, должности и специальности',visible:session.can('employees.view')},
  {id:'accounts',to:'/access',icon:'user',title:'Учётные записи',description:'Пользователи и назначение ролей',visible:session.canAccessDirectory},
  {id:'roles',to:'/roles',icon:'shield',title:'Роли и права',description:'Действия и области доступа',visible:session.canAny('access.roles.view','access.roles.manage')},
 ]},
 {id:'data',title:'Данные и документы',items:[
  {id:'references',to:'/references',icon:'book',title:'Справочники',description:'Отделы, должности и другие значения для выбора',visible:session.canAny('references.view','references.manage')},
  {id:'storage',to:'/settings/storage',icon:'folder',title:'Папки документов',description:'Папки по годам и доступ к файлам',visible:storage.value},
  {id:'imports',to:'/imports',icon:'file',title:'Источники журнала',description:'Загрузки, предпросмотр и сверка',visible:session.importPreviewEnabled&&session.can('imports.results.view')},
  {id:'source',to:'/imports/source-settings',icon:'table',title:'Google-таблица',description:'Ссылка на таблицу и лист',visible:source.value},
 ]},
].map(group=>({...group,items:group.items.filter(item=>item.visible)})).filter(group=>group.items.length))
</script>
<template>
 <div class="page-heading"><div><p class="eyebrow">Управление учреждением</p><h1>Настройки</h1><p class="muted">Сотрудники, доступ, данные и документы.</p></div></div>
 <nav aria-label="Разделы настроек" class="settings-directory" :class="{'settings-directory--single':groups.length===1}">
  <section v-for="group in groups" :key="group.id" class="settings-group" :aria-labelledby="`settings-${group.id}`">
   <h2 :id="`settings-${group.id}`" class="settings-group-title">{{group.title}}</h2>
   <ul class="settings-links">
    <li v-for="item in group.items" :key="item.id">
     <RouterLink :data-setting="item.id" :to="item.to" class="settings-entry">
      <UiIcon :name="item.icon" class="settings-icon"/>
      <span class="settings-entry-copy"><strong>{{item.title}}</strong><span>{{item.description}}</span></span>
      <UiIcon name="chevron-right" class="settings-chevron"/>
     </RouterLink>
    </li>
   </ul>
  </section>
 </nav>
 <p v-if="!storage&&session.can('access.roles.manage')" class="message">Для управления папками включите в нужной роли право «Настраивать папки документов» с областью «Учреждение». Новое право не выдаётся автоматически.</p>
</template>
<style scoped>
.settings-directory{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 40px;max-width:1200px;margin:26px 0 22px}
.settings-directory--single{grid-template-columns:minmax(0,1fr);max-width:580px}
.settings-group{min-width:0}
.settings-group+.settings-group{border-left:1px solid var(--border,#dce4d7);padding-left:40px}
.settings-directory .settings-group-title{margin:0 0 13px;font-size:11px;line-height:1.5;letter-spacing:1.5px;text-transform:uppercase;font-weight:700;color:var(--muted,#6e7f72)}
.settings-links{display:grid;gap:8px;list-style:none;padding:0;margin:0}
.settings-entry{display:flex;align-items:center;gap:14px;min-height:76px;padding:12px 14px;background:#fff;border:1px solid transparent;border-radius:6px;color:inherit;text-decoration:none;transition:background-color .15s,border-color .15s}
.settings-entry:hover{background:var(--surface-soft,#eef3e9);border-color:var(--border,#dce4d7)}
.settings-entry:focus-visible{outline:2px solid var(--green,#145b3e);outline-offset:3px;background:var(--surface-soft,#eef3e9)}
.settings-icon{width:25px;height:25px;flex:0 0 25px;color:var(--green,#145b3e)}
.settings-entry-copy{display:grid;gap:3px;min-width:0;flex:1}
.settings-entry-copy strong{font-size:15px;line-height:1.4;font-weight:600}
.settings-entry-copy>span{color:var(--muted,#6e7f72);font-size:12px;line-height:1.45;overflow-wrap:anywhere}
.settings-chevron{width:17px;height:17px;flex:0 0 17px;color:var(--muted,#6e7f72)}
@media(max-width:1100px){.settings-directory{gap:0 24px}.settings-group+.settings-group{padding-left:24px}.settings-entry{gap:11px;padding:11px 12px}}
@media(max-width:1000px){.settings-directory{grid-template-columns:minmax(0,1fr);gap:24px;max-width:680px;margin-top:22px}.settings-group+.settings-group{border-left:0;padding-left:0}}
@media(prefers-reduced-motion:reduce){.settings-entry{transition:none}}
</style>
