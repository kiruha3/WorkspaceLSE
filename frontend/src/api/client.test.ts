import { describe, expect, it } from 'vitest'
import { ApiClient, ApiError, LatestRequest } from './client'

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
})

describe('session API client', () => {
  it('gets CSRF before login and uses the rotated token on the next write', async () => {
    const calls: { path: string; init?: RequestInit }[] = []
    const client = new ApiClient(async (input, init) => {
      const path = String(input)
      calls.push({ path, init })
      if (path.endsWith('/csrf/')) return json({ csrf_token: 'before-login' })
      if (path.endsWith('/login/')) return json({ csrf_token: 'after-login' })
      return json({ id: 'role-1' }, 201)
    })
    await client.login('tester', 'local-test-secret')
    await client.request('/roles/', { method: 'POST', body: { name: 'Роль' } })
    expect(calls.map(c => c.path)).toEqual([
      '/api/v1/auth/csrf/', '/api/v1/auth/login/', '/api/v1/roles/',
    ])
    expect(new Headers(calls[1]?.init?.headers).get('X-CSRFToken')).toBe('before-login')
    expect(new Headers(calls[2]?.init?.headers).get('X-CSRFToken')).toBe('after-login')
    expect(calls[1]?.init?.credentials).toBe('same-origin')
    expect(JSON.parse(String(calls[1]?.init?.body))).toEqual({ username: 'tester', password: 'local-test-secret' })
  })

  it('rejects JSON errors with field details instead of returning successful data', async () => {
    const client = new ApiClient(async () => json({
      code: 'permission_denied', message: 'Доступ закрыт', field_errors: { name: ['Нет права'] },
    }, 403))
    await expect(client.request('/roles/')).rejects.toMatchObject({
      status: 403, code: 'permission_denied', message: 'Доступ закрыт', fieldErrors: { name: ['Нет права'] },
    })
    await expect(client.request('/roles/')).rejects.toBeInstanceOf(ApiError)
  })

  it('keeps a network failure as a rejected operation', async () => {
    const client = new ApiClient(async () => { throw new TypeError('offline') })
    await expect(client.request('/roles/')).rejects.toThrow('offline')
  })

  it('loads every reference page so choices beyond the first page remain available', async () => {
    const client = new ApiClient(async input => String(input).includes('page=2')
      ? json({ count: 2, next: null, previous: '/api/v1/references/specialties/?page=1', results: [{ id: 'second' }] })
      : json({ count: 2, next: '/api/v1/references/specialties/?page=2', previous: null, results: [{ id: 'first' }] }))
    expect(await client.allPages('/references/specialties/')).toEqual([{ id: 'first' }, { id: 'second' }])
  })
})

describe('latest request', () => {
  it('does not let a late list response replace a newer search result', async () => {
    let resolveOld!: (value: string[]) => void
    const old = new Promise<string[]>(resolve => { resolveOld = resolve })
    const request = new LatestRequest()
    let visible: string[] = []
    const first = request.run(() => old, value => { visible = value })
    await request.run(async () => ['Новая выборка'], value => { visible = value })
    resolveOld(['Старая выборка'])
    await first
    expect(visible).toEqual(['Новая выборка'])
  })
})
