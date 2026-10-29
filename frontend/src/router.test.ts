import { describe, expect, it } from 'vitest'
import { router } from './router'
import { setActivePinia } from 'pinia'
import { sessionWith } from './test/fixtures'
import { useSessionStore } from './stores/session'
describe('business routes', () => {
  it('allows an employee reader into Settings without granting other administrative access', async () => {
    const pinia = sessionWith('employees.view')
    setActivePinia(pinia)
    await router.push('/settings')
    expect(router.currentRoute.value.path).toBe('/settings')
    await router.push('/people')
    expect(router.currentRoute.value.path).toBe('/people')
    await router.push('/roles')
    expect(router.currentRoute.value.path).toBe('/workspace')
    const session = useSessionStore(pinia)
    session.user!.access = {}
    await router.push('/settings')
    expect(router.currentRoute.value.path).toBe('/workspace')
  })
  it('registers issue package routes with read and capability gates, including the explicit material entry', () => {
    for (const path of ['/issue-packages', '/issue-packages/new', '/issue-packages/package-1']) {
      const target = router.resolve(path)
      expect(target.meta.permission).toBe('issue.view')
      expect(target.meta.supportedModule).toBe('issuance')
    }
  })
  it('registers correspondence with independent read and server capability gates', () => {
    for (const path of ['/letters', '/letters/letter-1']) {
      const target = router.resolve(path)
      expect(target.meta.permission).toBe('letters.view')
      expect(target.meta.supportedModule).toBe('correspondence')
    }
  })
  it('registers intake and expertise routes with independent read permissions', () => {
    for (const [path, permission] of [['/intake', 'receipts.view'], ['/receipts/receipt-1', 'receipts.view'], ['/expertises', 'expertise.view'], ['/expertises/work-1', 'expertise.view']]) {
      const target = router.resolve(path!)
      expect(target.matched[0]?.path).not.toBe('/:pathMatch(.*)*')
      expect(target.meta.permission).toBe(permission)
    }
  })
})
