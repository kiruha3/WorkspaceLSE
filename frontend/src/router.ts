import { createRouter, createWebHistory } from 'vue-router'
import { useSessionStore,accessDirectoryActions } from './stores/session'
import HomePage from './modules/HomePage.vue'
import LoginPage from './modules/LoginPage.vue'
import RolesPage from './modules/RolesPage.vue'
import PeoplePage from './modules/PeoplePage.vue'
import AccessPeoplePage from './modules/AccessPeoplePage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workspace' },
    { path: '/login', component: LoginPage, meta: { title: 'Вход' } },
    { path: '/workspace', component: HomePage, meta: { title: 'Рабочее место' } },
    { path: '/roles', component: RolesPage, meta: { permissionsAny: ['access.roles.view','access.roles.manage'], title: 'Роли и права' } },
    { path: '/access', component: AccessPeoplePage, meta: { permissionsAny: accessDirectoryActions, title: 'Учётные записи' } },
    { path: '/people', component: PeoplePage, meta: { permission: 'employees.view', title: 'Сотрудники' } },
    { path: '/:pathMatch(.*)*', redirect: '/workspace' },
  ],
})
router.beforeEach(async to => {
  const session = useSessionStore()
  if (!session.ready) { try { await session.refresh() } catch { return to.path === '/login' ? true : '/login' } }
  if (!session.authenticated && to.path !== '/login') return '/login'
  if (to.meta.permission && !session.can(String(to.meta.permission))) return { path: '/workspace', query: { denied: '1' } }
  if (Array.isArray(to.meta.permissionsAny) && !session.canAny(...to.meta.permissionsAny)) return {path:'/workspace',query:{denied:'1'}}
  return true
})
