import { inject, type InjectionKey } from 'vue'
import type { Page } from './types'

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public fieldErrors: Record<string, unknown> = {}) { super(message); this.name = 'ApiError' }
}
interface Options { method?: string; body?: unknown; signal?: AbortSignal; headers?: HeadersInit }
export class ApiClient {
  private csrfToken = ''
  private csrfRequest: Promise<void> | null = null
  onUnauthorized?: () => void
  constructor(private transport: typeof fetch = (...args) => fetch(...args)) {}
  private failure(response: Response, data: unknown): ApiError {
    const error = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    if (response.status === 401) this.onUnauthorized?.()
    return new ApiError(response.status, typeof error.code === 'string' ? error.code : 'request_failed',
      typeof error.message === 'string' ? error.message : 'Не удалось выполнить запрос.',
      error.field_errors && typeof error.field_errors === 'object' ? error.field_errors as Record<string, unknown> : {})
  }
  private async ensureCsrf(): Promise<void> {
    if (this.csrfToken) return
    if (!this.csrfRequest) this.csrfRequest = this.request<{ csrf_token: string }>('/auth/csrf/')
      .then(result => { this.csrfToken = result.csrf_token })
      .finally(() => { this.csrfRequest = null })
    await this.csrfRequest
  }
  async request<T>(path: string, options: Options = {}): Promise<T> {
    const method = options.method ?? 'GET'
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) await this.ensureCsrf()
    const headers = new Headers(options.headers)
    headers.set('Accept', 'application/json')
    const multipart = options.body instanceof FormData
    if (multipart) headers.delete('Content-Type')
    else if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method.toUpperCase())) headers.set('X-CSRFToken', this.csrfToken)
    const response = await this.transport(`/api/v1${path}`, {
      method, headers, credentials: 'same-origin', signal: options.signal,
      body: options.body === undefined ? undefined : multipart ? options.body as FormData : JSON.stringify(options.body),
    })
    let data: unknown
    try { data = response.status === 204 ? undefined : await response.json() }
    catch { throw new ApiError(response.status, 'invalid_response', 'Сервер вернул некорректный ответ. Повторите запрос.') }
    if (!response.ok) throw this.failure(response, data)
    return data as T
  }
  async download(path: string, signal?: AbortSignal, fallbackFilename = '15-1.xlsx'): Promise<{ blob: Blob; filename: string }> {
    const mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    // DRF negotiates a renderer before the view returns its binary HttpResponse.
    // Also accept JSON for negotiation and errors; successful files still require XLSX.
    const response = await this.transport(`/api/v1${path}`, { credentials: 'same-origin', signal, headers: { Accept: `${mime}, application/json` }, cache: 'no-store' })
    if (!response.ok) throw this.failure(response, await response.json().catch(() => null))
    if (!response.headers.get('Content-Type')?.startsWith(mime)) throw new ApiError(response.status, 'invalid_response', 'Сервер вернул ответ не в формате Excel. Повторите выгрузку.')
    const name = /filename="?([A-Za-z0-9_.-]+\.xlsx)"?/.exec(response.headers.get('Content-Disposition') ?? '')?.[1]
    return { blob: await response.blob(), filename: name ?? fallbackFilename }
  }
  async login(username: string, password: string): Promise<void> {
    const result = await this.request<{ csrf_token: string }>('/auth/login/', { method: 'POST', body: { username, password } })
    this.csrfToken = result.csrf_token
  }
  async allPages<T>(path: string, signal?: AbortSignal): Promise<T[]> {
    const items: T[] = []
    let page = 1, hasMore = true
    while (hasMore) {
      const response = await this.request<Page<T>>(`${path}${path.includes('?') ? '&' : '?'}page=${page}`, { signal })
      items.push(...response.results)
      hasMore = Boolean(response.next)
      page++
    }
    return items
  }
  async logout(): Promise<void> {
    await this.request('/auth/logout/', { method: 'POST' })
    this.csrfToken = ''
  }
}
export class LatestRequest {
  private revision = 0
  private controller?: AbortController
  cancel(): void { this.revision++; this.controller?.abort() }
  async run<T>(load: (signal: AbortSignal) => Promise<T>, apply: (result: T) => void): Promise<void> {
    this.cancel()
    const revision = this.revision
    this.controller = new AbortController()
    try {
      const value = await load(this.controller.signal)
      if (revision === this.revision) apply(value)
    } catch (error) { if (revision === this.revision) throw error }
  }
}
export const api = new ApiClient()
export const apiKey: InjectionKey<ApiClient> = Symbol('api')
export const useApi = () => inject(apiKey, api)
