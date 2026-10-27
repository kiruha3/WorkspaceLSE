import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { ApiClient, apiKey } from '../api/client'
import { json, page, role, sessionWith } from '../test/fixtures'
import RolesPage from './RolesPage.vue'

const catalog = [
  { code: 'employees.view', label: 'Просмотр сотрудников', module: 'Сотрудники', scopes: ['departments', 'institution'] },
  { code: 'specialties.qualify', label: 'Подтвердить квалификацию', module: 'Специальности', scopes: ['departments', 'institution'] },
]
function setup(conflict = false) {
  const writes: { path: string; body: unknown }[] = []
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
  const wrapper = mount(RolesPage, { global: { plugins: [sessionWith('access.roles.view', 'access.roles.manage')], provide: { [apiKey as symbol]: client } } })
  return { wrapper, writes }
}

describe('roles editor', () => {
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
