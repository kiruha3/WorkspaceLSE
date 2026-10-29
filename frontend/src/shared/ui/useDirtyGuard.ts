import { onBeforeUnmount } from 'vue'
import type { Router } from 'vue-router'

const dirtyForms = new Set<() => boolean>()
const busyForms = new Set<() => boolean>()
export const hasDirtyForms = () => [...dirtyForms].some(isDirty => isDirty())
export const hasBusyForms = () => [...busyForms].some(isBusy => isBusy())

export function useDirtyGuard(isDirty: () => boolean, router?: Router, isBusy: () => boolean = () => false) {
  dirtyForms.add(isDirty)
  busyForms.add(isBusy)
  const confirmLeave = () => !isBusy() && (!isDirty() || window.confirm('Есть несохранённые изменения. Покинуть форму?'))
  const beforeUnload = (event: BeforeUnloadEvent) => { if (isDirty() || isBusy()) { event.preventDefault(); event.returnValue = '' } }
  window.addEventListener('beforeunload', beforeUnload)
  const removeGuard = router?.beforeEach(() => confirmLeave())
  onBeforeUnmount(() => { dirtyForms.delete(isDirty); busyForms.delete(isBusy); window.removeEventListener('beforeunload', beforeUnload); removeGuard?.() })
  return confirmLeave
}
