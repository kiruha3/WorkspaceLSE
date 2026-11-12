import { onBeforeUnmount } from 'vue'

/** Debounce typed searches while invalidating results for the previous query. */
export function useLiveSearch(apply: () => unknown, invalidate: () => void, delay = 300) {
  let timer: ReturnType<typeof setTimeout> | undefined
  function cancel() {
    if (timer !== undefined) clearTimeout(timer)
    timer = undefined
  }
  function schedule(event?: Event) {
    cancel()
    invalidate()
    if (event && 'isComposing' in event && event.isComposing) return
    timer = setTimeout(() => { timer = undefined; void apply() }, delay)
  }
  onBeforeUnmount(cancel)
  return { schedule, cancel }
}
