import type {CurrentUser} from './types'
export const reportPlanReadActions=['references.view','references.manage','reports.form151.run','reports.plans.manage']
export const institutionPermission=(user:CurrentUser|null,action:string)=>Boolean(user?.access[action]?.some(rule=>rule.scope==='institution'&&rule.scope_limit==='institution'))
export const canReadReportPlans=(user:CurrentUser|null)=>reportPlanReadActions.some(action=>institutionPermission(user,action))
export const canManageReportPlans=(user:CurrentUser|null)=>institutionPermission(user,'reports.plans.manage')
