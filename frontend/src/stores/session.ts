import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, ApiError } from '../api/client'
import type { CurrentUser } from '../api/types'

export const accessDirectoryActions = ['users.view','users.create','users.deactivate','access.roles.assign','access.effective.view']

export const useSessionStore = defineStore('session', () => {
  const user = ref<CurrentUser | null>(null)
  const ready = ref(false)
  const error = ref('')
  const authenticated = computed(() => user.value !== null)
  const can = (code: string): boolean => Boolean(user.value?.access[code]?.length)
  const canAny = (...codes:string[]):boolean => codes.some(can)
  const canAccessDirectory = computed(()=>canAny(...accessDirectoryActions))
  const correspondenceEnabled = computed(() => Boolean(user.value?.supported_modules?.includes('correspondence')))
  api.onUnauthorized = () => { user.value = null }
  async function refresh(): Promise<void> {
    error.value = ''
    try { user.value = await api.request<CurrentUser>('/me/') }
    catch (cause) {
      user.value = null
      if (!(cause instanceof ApiError && cause.status === 401)) {
        error.value = 'Не удалось проверить сессию. Проверьте соединение и повторите.'
        throw cause
      }
    } finally { ready.value = true }
  }
  async function login(username: string, password: string): Promise<void> {
    await api.login(username, password)
    await refresh()
  }
  async function logout(): Promise<void> {
    await api.logout()
    user.value = null
    ready.value = true
  }
  return { user, ready, error, authenticated, can, canAny, canAccessDirectory, correspondenceEnabled, refresh, login, logout }
})
