import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, apiKey } from '../api/client'
import { json, page, role, sessionWith } from '../test/fixtures'
import RolesPage from './RolesPage.vue'

enableAutoUnmount(afterEach)
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

const catalog = [
  { code: 'employees.view', label: 'Просмотр сотрудников', module: 'Сотрудники', scopes: ['departments', 'institution'] },
  { code: 'specialties.qualify', label: 'Подтвердить квалификацию', module: 'Специальности', scopes: ['departments', 'institution'] },
]
function setup(conflict = false, captureErrors = false) {
  const writes: { path: string; body: unknown }[] = []
  const errors: unknown[] = []
  const client = new ApiClient(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/csrf/')) return json({ csrf_token: 'test-token' })
    if (init?.method === 'PUT') {
      writes.push({ path, body: JSON.parse(String(init.body)) })
      return conflict ? json({ code: 'version_conflict', message: 'Роль уже изменена.', field_errors: {} }, 409) : json({ ...role, version: 5, permissions: [{ permission_code: 'employees.view', scope: 'institution' }] })
    }
    if (path.endsWith('/permissions/')) return json(catalog)
    return json(page([role]))
  })
  const wrapper = mount(RolesPage, { global: { config: captureErrors ? { errorHandler: cause => errors.push(cause) } : {}, plugins: [sessionWith('access.roles.view', 'access.roles.manage')], provide: { [apiKey as symbol]: client } } })
  return { wrapper, writes, errors }
}

describe('roles editor', () => {
  it('opens the selected role when its status cell is clicked, without writing permissions',async()=>{
    const {wrapper,writes}=setup()
    await flushPromises()
    await wrapper.get('tbody tr td:last-child').trigger('click')
    expect(wrapper.find('[aria-label="Редактор роли"]').exists()).toBe(true)
    expect(wrapper.get('[name="role_name"]').element).toHaveProperty('value','Руководитель и эксперт')
    expect(wrapper.find('.editor-empty').exists()).toBe(false)
    expect(writes).toEqual([])
  })
  it('opens and edits roles without structuredClone, preserving the saved permission baseline',async()=>{
    vi.stubGlobal('structuredClone',undefined)
    const {wrapper,writes,errors}=setup(false,true)
    await flushPromises()
    await wrapper.get('[data-role="role-1"]').trigger('click')
    expect(wrapper.find('[aria-label="Редактор роли"]').exists()).toBe(true)
    expect(errors).toEqual([])
    await wrapper.get('[data-scope="employees.view"]').setValue('institution')
    expect(wrapper.get('[data-save-permissions]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('.change-preview').text()).toContain('Выбранные отделы → Учреждение')
    expect(role.permissions).toEqual([{permission_code:'employees.view',scope:'departments'}])
    expect(writes).toEqual([])
  })
  it('opens the editor instead of leaving it below a long registry and can return to the list',async()=>{
    const {wrapper}=setup()
    await flushPromises()
    await wrapper.get('[data-role="role-1"]').trigger('click')
    expect(wrapper.find('[aria-label="Реестр ролей"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Редактор роли"]').exists()).toBe(true)
    await wrapper.get('[data-back-roles]').trigger('click')
    expect(wrapper.find('[data-role="role-1"]').exists()).toBe(true)
    wrapper.unmount()
  })
  it('groups supported actions and saves their explicit scope with the expected version', async () => {
    const { wrapper, writes } = setup()
    await flushPromises()
    expect(wrapper.text()).toContain('Руководитель и эксперт')
    await wrapper.get('[data-role="role-1"]').trigger('click')
    expect(wrapper.get('[data-permission-group="Сотрудники"]').text()).toContain('Просмотр сотрудников')
    await wrapper.get('[data-scope="employees.view"]').setValue('institution')
    await wrapper.get('[data-save-permissions]').trigger('click')
    await flushPromises()
    expect(writes).toEqual([{ path: '/api/v1/roles/role-1/permissions/', body: { expected_version: 4, permissions: [{ permission_code: 'employees.view', scope: 'institution' }] } }])
    expect(wrapper.get('[role="status"]').text()).toContain('сохранены')
  })

  it('retains a permission draft and shows a conflict instead of success when the version is stale', async () => {
    const { wrapper } = setup(true)
    await flushPromises()
    expect(wrapper.text()).toContain('Руководитель и эксперт')
    await wrapper.get('[data-role="role-1"]').trigger('click')
    await wrapper.get('[data-scope="employees.view"]').setValue('institution')
    await wrapper.get('[data-save-permissions]').trigger('click')
    await flushPromises()
    expect((wrapper.get('[data-scope="employees.view"]').element as HTMLSelectElement).value).toBe('institution')
    expect(wrapper.get('[role="alert"]').text()).toContain('Конфликт')
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })
})
