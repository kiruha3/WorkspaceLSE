import { createRouter, createWebHistory } from 'vue-router'
import { useSessionStore,accessDirectoryActions } from './stores/session'
import HomePage from './modules/HomePage.vue'
import LoginPage from './modules/LoginPage.vue'
import RolesPage from './modules/RolesPage.vue'
import PeoplePage from './modules/PeoplePage.vue'
import AccessPeoplePage from './modules/AccessPeoplePage.vue'
import IntakePage from './modules/intake/IntakePage.vue'
import ReceiptPage from './modules/intake/ReceiptPage.vue'
import ExpertisesPage from './modules/expertises/ExpertisesPage.vue'
import ExpertisePage from './modules/expertises/ExpertisePage.vue'
import LettersPage from './modules/letters/LettersPage.vue'
import LetterPage from './modules/letters/LetterPage.vue'
import IssuePackagesPage from './modules/issuance/IssuePackagesPage.vue'
import IssuePackagePage from './modules/issuance/IssuePackagePage.vue'
import ImportPreviewsPage from './modules/imports/ImportPreviewsPage.vue'
import ImportPreviewPage from './modules/imports/ImportPreviewPage.vue'
import ReconciliationPage from './modules/imports/ReconciliationPage.vue'
import ReportsPage from './modules/reports/ReportsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/workspace' },
    { path: '/login', component: LoginPage, meta: { title: 'Вход' } },
    { path: '/workspace', component: HomePage, meta: { title: 'Рабочее место' } },
    { path: '/reports', component: ReportsPage, meta: { permissionsAny: ['reports.form151.run'], title: 'Отчёт 15.1' } },
    { path: '/intake', component: IntakePage, meta: { permission: 'receipts.view', title: 'Приёмка материалов' } },
    { path: '/receipts/:id', component: ReceiptPage, meta: { permission: 'receipts.view', title: 'Поступление' } },
    { path: '/expertises', component: ExpertisesPage, meta: { permission: 'expertise.view', title: 'Реестр экспертиз' } },
    { path: '/expertises/:id', component: ExpertisePage, meta: { permission: 'expertise.view', title: 'Рабочая карточка' } },
    { path: '/letters', component: LettersPage, meta: { permission: 'letters.view', supportedModule: 'correspondence', title: 'Журнал переписки' } },
    { path: '/letters/:id', component: LetterPage, meta: { permission: 'letters.view', supportedModule: 'correspondence', title: 'Карточка письма' } },
    { path: '/issue-packages', component: IssuePackagesPage, meta: { permission: 'issue.view', supportedModule: 'issuance', title: 'Журнал выдачи' } },
    { path: '/issue-packages/new', component: IssuePackagePage, meta: { permission: 'issue.view', supportedModule: 'issuance', title: 'Подготовка комплекта' } },
    { path: '/issue-packages/:id', component: IssuePackagePage, meta: { permission: 'issue.view', supportedModule: 'issuance', title: 'Комплект материала' } },
    { path: '/roles', component: RolesPage, meta: { permissionsAny: ['access.roles.view','access.roles.manage'], title: 'Роли и права' } },
    { path: '/imports', component: ImportPreviewsPage, meta: { permission: 'imports.results.view', supportedModule: 'journal_import_preview', title: 'Источники журнала' } },
    { path: '/imports/:id', component: ImportPreviewPage, meta: { permission: 'imports.results.view', supportedModule: 'journal_import_preview', title: 'Предпросмотр переноса' } },
    { path: '/imports/:id/reconciliation', component: ReconciliationPage, meta: { permission: 'imports.results.view', supportedModule: 'journal_application', title: 'Сверка журнала' } },
    { path: '/access', component: AccessPeoplePage, meta: { permissionsAny: accessDirectoryActions, title: 'Учётные записи' } },
    { path: '/people', component: PeoplePage, meta: { permission: 'employees.view', title: 'Сотрудники' } },
    { path: '/:pathMatch(.*)*', redirect: '/workspace' },
  ],
})
router.beforeEach(async to => {
  const session = useSessionStore()
  if (!session.ready) { try { await session.refresh() } catch { return to.path === '/login' ? true : '/login' } }
  if (!session.authenticated && to.path !== '/login') return '/login'
  if (to.meta.supportedModule === 'correspondence' && !session.correspondenceEnabled) return { path: '/workspace', query: { denied: '1' } }
  if (to.meta.supportedModule === 'issuance' && !session.issuanceEnabled) return { path: '/workspace', query: { denied: '1' } }
  if (to.meta.supportedModule === 'journal_import_preview' && !session.importPreviewEnabled) return { path: '/workspace', query: { denied: '1' } }
  if (to.meta.supportedModule === 'journal_application' && (!session.journalApplicationEnabled || !session.importPreviewEnabled)) return { path: '/workspace', query: { denied: '1' } }
  if (to.meta.permission && !session.can(String(to.meta.permission))) return { path: '/workspace', query: { denied: '1' } }
  if (Array.isArray(to.meta.permissionsAny) && !session.canAny(...to.meta.permissionsAny)) return {path:'/workspace',query:{denied:'1'}}
  return true
})
