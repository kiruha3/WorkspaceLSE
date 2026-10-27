import { computed, ref, watch, type Ref } from 'vue'
import { ApiError, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { IssueCommandResponse } from '../../api/issuance'
export function useIssueAttempt(stamp: Ref<string>) {
  const api = useApi(), busy = ref(false), error = ref<unknown>(null), uncertain = ref(false)
  const attempt = ref<{ path: string; body: Record<string, unknown>; key: string } | null>(null)
  function reset() { attempt.value = null; uncertain.value = false; error.value = null }
  watch(stamp, reset, { flush: 'sync' })
  const recovering = computed(() => Boolean(attempt.value && uncertain.value))
  async function execute(path: string, prepare: () => Promise<Record<string, unknown>>): Promise<IssueCommandResponse | null> {
    if (busy.value) return null
    busy.value = true; error.value = null
    try {
      if (!attempt.value) attempt.value = { path, body: await prepare(), key: newCommandKey() }
      const response = await api.request<IssueCommandResponse>(attempt.value.path, { method: 'POST', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
      reset(); return response
    } catch (cause) { error.value = cause; uncertain.value = Boolean(attempt.value) && (!(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response'); return null }
    finally { busy.value = false }
  }
  return { attempt, busy, error, recovering, reset, execute }
}
