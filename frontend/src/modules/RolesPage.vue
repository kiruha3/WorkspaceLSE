<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, ref, toRaw } from 'vue'
import { routerKey } from 'vue-router'
import { LatestRequest, useApi } from '../api/client'
import type { Page, PermissionDefinition, Role, RolePermission, Scope } from '../api/types'
import { useSessionStore } from '../stores/session'
import ApiMessage from '../shared/ui/ApiMessage.vue'
import PaginationBar from '../shared/ui/PaginationBar.vue'
import { useDirtyGuard } from '../shared/ui/useDirtyGuard'

const api = useApi()
const session = useSessionStore()
const canManage = computed(() => session.can('access.roles.manage'))
const list = ref<Page<Role>>({ count: 0, next: null, previous: null, results: [] })
const catalog = ref<PermissionDefinition[]>([])
const selected = ref<Role | null>(null)
const editing = ref(false)
const name = ref(''), description = ref(''), active = ref(true)
const permissions = ref<Record<string, Scope | ''>>({})
const error = ref<unknown>(null), listError = ref<unknown>(null), success = ref('')
const loading = ref(false), saving = ref(false), page = ref(1), search = ref('')
const listRequest = new LatestRequest()
const scopes: Record<Scope, string> = { own: 'Свои', departments: 'Выбранные отделы', institution: 'Учреждение' }
const permissionList = computed<RolePermission[]>(() => Object.entries(permissions.value).filter((entry): entry is [string, Scope] => Boolean(entry[1])).map(([permission_code, scope]) => ({ permission_code, scope })))
const groups = computed(() => {
  const result: Record<string, PermissionDefinition[]> = {}
  for (const permission of catalog.value) (result[permission.module] ??= []).push(permission)
  return result
})
const metadataDirty = computed(() => editing.value && (name.value !== (selected.value?.name ?? '') || description.value !== (selected.value?.description ?? '') || active.value !== (selected.value?.is_active ?? true)))
const permissionsDirty = computed(() => JSON.stringify([...permissionList.value].sort((a,b) => a.permission_code.localeCompare(b.permission_code))) !== JSON.stringify([...(selected.value?.permissions ?? [])].sort((a,b) => a.permission_code.localeCompare(b.permission_code))))
const dirty = computed(() => editing.value && (metadataDirty.value || permissionsDirty.value))
const confirmLeave = useDirtyGuard(() => dirty.value, inject(routerKey, undefined))
const differences = computed(() => {
  const before = new Map((selected.value?.permissions ?? []).map(p => [p.permission_code, p.scope]))
  return catalog.value.flatMap(p => {
    const was = before.get(p.code), now = permissions.value[p.code]
    if (was === now || (!was && !now)) return []
    return [`${p.label}: ${was ? scopes[was] : 'нет'} → ${now ? scopes[now] : 'нет'}`]
  })
})
async function load(nextPage = page.value) {
  page.value = nextPage; loading.value = true; listError.value = null
  try { await listRequest.run(signal => api.request<Page<Role>>(`/roles/?${new URLSearchParams({ page: String(page.value), search: search.value })}`, { signal }), result => { list.value = result; loading.value = false }) }
  catch (cause) { listError.value = cause; loading.value = false }
}
function edit(role: Role | null) {
  if (saving.value || !confirmLeave()) return
  selected.value = role ? structuredClone(toRaw(role)) : null
  name.value = role?.name ?? ''; description.value = role?.description ?? ''; active.value = role?.is_active ?? true
  permissions.value = Object.fromEntries((role?.permissions ?? []).map(p => [p.permission_code, p.scope]))
  error.value = null; success.value = ''; editing.value = true
}
function closeEditor() {
  if (saving.value || !confirmLeave()) return
  editing.value = false; selected.value = null; error.value = null; success.value = ''
}
function remember(role: Role) {
  const index = list.value.results.findIndex(item => item.id === role.id)
  if (index >= 0) list.value.results[index] = role
  else { list.value.results.unshift(role); list.value.count++ }
  selected.value = role
}
async function save(part: 'details' | 'permissions' | 'new') {
  if (saving.value || !canManage.value || !editing.value) return
  saving.value = true; error.value = null; success.value = ''
  try {
    const role = await api.request<Role>(part === 'new' ? '/roles/' : part === 'permissions' ? `/roles/${selected.value!.id}/permissions/` : `/roles/${selected.value!.id}/`, {
      method: part === 'new' ? 'POST' : part === 'permissions' ? 'PUT' : 'PATCH',
      body: part === 'new' ? { name: name.value.trim(), description: description.value, permissions: permissionList.value }
        : part === 'permissions' ? { expected_version: selected.value!.version, permissions: permissionList.value }
        : { expected_version: selected.value!.version, name: name.value.trim(), description: description.value, is_active: active.value },
    })
    remember(role)
    if (part !== 'permissions') { name.value = role.name; description.value = role.description; active.value = role.is_active }
    if (part !== 'details') permissions.value = Object.fromEntries(role.permissions.map(p => [p.permission_code, p.scope]))
    success.value = part === 'permissions' ? 'Права сохранены сервером.' : part === 'new' ? 'Роль создана сервером.' : 'Сведения сохранены сервером.'
  } catch (cause) { error.value = cause }
  finally { saving.value = false }
}
async function reloadSelected() {
  if (!selected.value || !confirmLeave()) return
  try {
    const role = await api.request<Role>(`/roles/${selected.value.id}/`)
    editing.value = false; remember(role); edit(role)
  } catch (cause) { error.value = cause }
}
onMounted(async () => {
  void load()
  if (canManage.value) try { catalog.value = await api.request<PermissionDefinition[]>('/permissions/') } catch (cause) { error.value = cause }
})
onBeforeUnmount(() => listRequest.cancel())
</script>

<template>
  <div class="page-heading"><div><p class="eyebrow">Управление доступом</p><h1>Роли и права</h1><p class="muted">Поддерживаемые действия, явные области и несколько ролей у одного сотрудника.</p></div><button v-if="editing" data-back-roles :disabled="saving" @click="closeEditor">← К списку ролей</button><button v-else-if="canManage" class="button-primary" :disabled="saving" @click="edit(null)">+ Создать роль</button></div>
  <div :class="{'split-layout':!editing}">
    <section v-if="!editing" class="card registry-pane" aria-label="Реестр ролей">
      <form class="toolbar" @submit.prevent="load(1)"><label class="grow">Поиск ролей<input v-model="search" placeholder="Название или назначение" type="search" /></label><button :disabled="loading">Найти</button></form>
      <ApiMessage :error="listError" />
      <p v-if="loading" class="state" aria-live="polite">Загрузка ролей…</p>
      <div v-else class="table-scroll"><table><thead><tr><th>Роль</th><th>Назначения</th><th>Состояние</th></tr></thead><tbody>
        <tr v-for="role in list.results" :key="role.id" :class="{ 'row-selected': selected?.id === role.id }"><td><button class="text-button" :data-role="role.id" @click="edit(role)">{{ role.name }}</button><small>{{ role.description || 'Описание не указано' }}</small></td><td>{{ role.assignment_count }}</td><td><span class="badge" :class="role.is_active ? 'badge-green' : ''">{{ role.is_active ? 'Активна' : 'Неактивна' }}</span><small>Версия {{ role.version }}</small></td></tr>
        <tr v-if="!list.results.length"><td colspan="3" class="state">Ролей по этой выборке нет.</td></tr>
      </tbody></table></div>
      <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="load" />
    </section>
    <section v-if="editing" class="card editor-pane" aria-label="Редактор роли">
      <div class="section-heading"><div><p class="eyebrow">{{ selected ? `Версия ${selected.version} · назначений ${selected.assignment_count}` : 'Новая роль' }}</p><h2>{{ selected?.name ?? 'Создание роли' }}</h2></div><span v-if="dirty" class="badge badge-amber">Есть изменения</span></div>
      <ApiMessage :error="error" /><p v-if="success" class="message message-success" role="status">{{ success }}</p>
      <fieldset :disabled="!canManage || saving"><form class="form-grid" @submit.prevent="save(selected ? 'details' : 'new')">
        <label>Название роли<input v-model="name" name="role_name" required maxlength="150" /></label>
        <label>Назначение<textarea v-model="description" name="role_description" rows="2" /></label>
        <label v-if="selected" class="check-label"><input v-model="active" type="checkbox" />Роль активна</label>
        <div v-if="selected" class="button-row"><button class="button-primary" :disabled="!metadataDirty">Сохранить сведения</button><button type="button" @click="reloadSelected">Загрузить серверную версию</button></div>
      </form></fieldset>
      <h3>Права по модулям</h3><p class="muted compact">Область задаётся для каждого действия. Должность и название роли прав не выдают.</p>
      <fieldset :disabled="!canManage || saving">
        <section v-for="(items, module) in groups" :key="module" class="permission-group" :data-permission-group="module"><h4>{{ module }}</h4>
          <div v-for="permission in items" :key="permission.code" class="permission-row"><label class="check-label"><input type="checkbox" :checked="Boolean(permissions[permission.code])" @change="permissions[permission.code] = ($event.target as HTMLInputElement).checked ? permission.scopes[0]! : ''" />{{ permission.label }}<small>{{ permission.code }}</small></label><label class="scope-field"><span class="sr-only">Область: {{ permission.label }}</span><select v-model="permissions[permission.code]" :data-scope="permission.code" :disabled="!permissions[permission.code]"><option value="">Не разрешено</option><option v-for="scope in permission.scopes" :key="scope" :value="scope">{{ scopes[scope] }}</option></select></label></div>
        </section>
        <div v-if="!catalog.length" class="state"><p v-for="permission in selected?.permissions" :key="permission.permission_code">{{ permission.permission_code }} · {{ scopes[permission.scope] }}</p><p>Каталог редактирования доступен при праве управления ролями.</p></div>
        <div v-if="differences.length" class="change-preview"><h4>Изменения перед сохранением</h4><ul><li v-for="difference in differences" :key="difference">{{ difference }}</li></ul></div>
        <button v-if="canManage" class="button-primary" data-save-permissions :disabled="saving || !catalog.length || (selected ? !permissionsDirty : !name.trim())" @click="save(selected ? 'permissions' : 'new')">{{ saving ? 'Сохранение…' : selected ? 'Сохранить права' : 'Создать роль с этими правами' }}</button>
      </fieldset>
    </section>
    <section v-else class="card editor-empty"><span class="empty-symbol">◇</span><h2>Выберите роль</h2><p class="muted">В редакторе появятся действия, области и число назначений. Изменения применяются после подтверждения сервера.</p></section>
  </div>
</template>
