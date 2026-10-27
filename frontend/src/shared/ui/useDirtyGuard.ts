import { onBeforeUnmount } from 'vue'
import type { Router } from 'vue-router'

const dirtyForms = new Set<() => boolean>()
export const hasDirtyForms = () => [...dirtyForms].some(isDirty => isDirty())

export function useDirtyGuard(isDirty: () => boolean, router?: Router) {
  dirtyForms.add(isDirty)
  const confirmLeave = () => !isDirty() || window.confirm('Есть несохранённые изменения. Покинуть форму?')
  const beforeUnload = (event: BeforeUnloadEvent) => { if (isDirty()) { event.preventDefault(); event.returnValue = '' } }
  window.addEventListener('beforeunload', beforeUnload)
  const removeGuard = router?.beforeEach(() => confirmLeave())
  onBeforeUnmount(() => { dirtyForms.delete(isDirty); window.removeEventListener('beforeunload', beforeUnload); removeGuard?.() })
  return confirmLeave
}
