import { describe, expect, it } from 'vitest'
import { router } from './router'
describe('business routes', () => {
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
