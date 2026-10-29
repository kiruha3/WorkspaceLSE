<script setup lang="ts">
import SortableTable from '../../shared/ui/SortableTable.vue'
import {orderingParams} from '../../shared/ui/tableSorting'
import {useRouteTableSort} from '../../shared/ui/useRouteTableSort'

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import type { Page, Receipt, Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import PaginationBar from '../../shared/ui/PaginationBar.vue'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import HelpTip from '../../shared/ui/HelpTip.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const {ordering,sortTable}=useRouteTableSort()
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter()
const list = ref<Page<Receipt>>({ count: 0, next: null, previous: null, results: [] }), loading = ref(false), error = ref<unknown>(null)
const search = ref(String(route.query.search ?? '')), page = computed(() => Math.max(1, Number(route.query.page) || 1))
const creating = ref(false), receivedAt = ref(''), sender = ref(''), materialTitle = ref(''), departmentId = ref(''), withBasis = ref(true)
const isDemo = ref(false)
const departments = ref<Reference[]>([]), basisForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null), saving = ref(false), saved = ref(false)
const createError = ref<unknown>(null), referencesError = ref<unknown>(null), requests = new LatestRequest()
const dirty = computed(() => creating.value && !saved.value && Boolean(receivedAt.value || sender.value || materialTitle.value || departmentId.value || isDemo.value || basisForm.value?.dirty))
const confirmLeave = useDirtyGuard(() => dirty.value || saving.value, router)
async function load() {
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<Page<Receipt>>(`/receipts/?${new URLSearchParams({...orderingParams(ordering.value), search: String(route.query.search ?? ''), page: String(page.value) })}`, { signal }), result => { list.value = result; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function filter(nextPage = 1) { await router.replace({ path: '/intake', query: {...orderingParams(ordering.value), ...(search.value ? { search: search.value } : {}), page: String(nextPage) } }) }
async function startCreate() {
  creating.value = true; saved.value = false; createError.value = null
  if (!departments.value.length) try { departments.value = await api.allPages<Reference>('/references/departments/') } catch (cause) { referencesError.value = cause }
}
function back() { if (!saving.value && confirmLeave()) creating.value = false }
async function create() {
  if (saving.value || !session.can('receipts.create')) return
  saving.value = true; createError.value = null
  try {
    const document = withBasis.value && session.can('documents.upload') ? await basisForm.value?.persist() : null
    const result = await api.request<Receipt>('/receipts/', { method: 'POST', body: { received_at: receivedAt.value, sender_name: sender.value.trim(), material_title: materialTitle.value.trim(), department_id: departmentId.value || null, ...(isDemo.value ? { is_demo: true } : {}), ...(document ? { basis_document_id: document.id } : {}) } })
    saved.value = true; saving.value = false
    await router.push({ path: `/receipts/${result.id}`, query: { return: route.fullPath } })
  } catch (cause) { createError.value = cause } finally { saving.value = false }
}
watch(() => route.fullPath, () => { if (route.path === '/intake') void load() })
onMounted(load)
onBeforeUnmount(() => requests.cancel())
</script>
<template>
  <div class="intake-compact intake-page">
    <button v-if="creating" class="text-button receipt-back" :disabled="saving" @click="back">← К поступлениям</button>
    <header class="receipt-heading">
      <div>
        <p class="eyebrow">Делопроизводство</p>
        <div class="receipt-title">
          <h1>{{ creating ? 'Новое поступление' : 'Приёмка материалов' }}</h1>
          <HelpTip label="Приёмка материалов">Поступление и материал сохраняются до закрепления номера экспертизы. Сначала укажите сведения и основание, затем примите поступление и зарегистрируйте работу в его карточке.</HelpTip>
          <span v-if="creating && dirty" class="badge badge-amber">Есть изменения</span>
        </div>
      </div>
      <button v-if="!creating && session.can('receipts.create')" data-new-receipt class="button-primary" @click="startCreate">+ Новое поступление</button>
    </header>
    <section v-if="!creating" class="card intake-registry">
      <form class="toolbar intake-toolbar" @submit.prevent="filter()">
        <label class="search-field">Поиск поступлений<input v-model="search" type="search" placeholder="Отправитель или материал" /></label>
        <button :disabled="loading">Найти</button>
        <span class="muted intake-count" role="status">{{ loading ? 'Загрузка…' : `Найдено: ${list.count}` }}</span>
      </form>
      <ApiMessage :error="error" />
      <p v-if="loading" class="state">Загрузка поступлений…</p>
      <div v-else class="table-scroll">
        <SortableTable :rows="list.results" :columns='[{"key": "received_at", "label": "Поступление"}, {"key": "sender_name", "label": "Отправитель"}, {"key": "material", "label": "Материал"}, {"key": "basis", "label": "Основание"}, {"key": "status", "label": "Приёмка"}]' :ordering="ordering" @update:ordering="sortTable" v-slot="{rows:tableRows}">
            <tr v-for="item in tableRows" :key="item.id">
              <td><RouterLink :to="{ path: `/receipts/${item.id}`, query: { return: route.fullPath } }">{{ item.received_at }}</RouterLink><small>№ поступления {{ item.id.slice(0, 8) }}</small></td>
              <td>{{ item.sender_name || 'Не указан' }}</td>
              <td>{{ item.material.title || 'Без названия' }}</td>
              <td>{{ item.basis_document ? 'restricted' in item.basis_document ? 'Доступ ограничен' : item.basis_document.title : 'Не указано' }}</td>
              <td><span class="badge" :class="item.status === 'accepted' ? 'badge-green' : 'badge-amber'">{{ item.status === 'historical' ? 'Историческое поступление' : item.status === 'accepted' ? 'Принято' : 'Черновик' }}</span></td>
            </tr>
            <tr v-if="!list.results.length"><td colspan="5" class="state">Поступлений по этой выборке нет.</td></tr>
          </SortableTable>
      </div>
      <PaginationBar :page="page" :count="list.count" :next="Boolean(list.next)" :previous="Boolean(list.previous)" :busy="loading" @change="filter" />
    </section>
    <template v-else>
      <ApiMessage :error="createError" />
      <ApiMessage :error="referencesError" />
      <form data-create-receipt class="form-grid" @submit.prevent="create">
        <fieldset class="receipt-create-layout" :disabled="saving">
          <section class="card form-grid">
            <h2>Сведения поступления</h2>
            <div class="form-columns">
              <label>Дата поступления<input v-model="receivedAt" name="received_at" type="date" required /></label>
              <label>Первоначальный отдел<select v-model="departmentId" name="department_id" required><option value="">Выберите отдел явно</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label>
            </div>
            <label>Отправитель, если известен<input v-model="sender" name="sender_name" /></label>
            <label>Название материала<input v-model="materialTitle" name="material_title" /></label>
            <div class="button-row intake-training">
              <label class="check-label"><input v-model="isDemo" name="is_demo" type="checkbox" />Учебное поступление</label>
              <HelpTip label="Учебное поступление">Все экспертизы этого материала исключаются из отчёта 15.1. Для рабочих материалов оставьте флажок выключенным.</HelpTip>
            </div>
            <p v-if="isDemo" class="message">Экспертизы этого материала не войдут в отчёт 15.1.</p>
          </section>
          <section class="card form-grid">
            <h2>Документ-основание</h2>
            <label v-if="session.can('documents.upload')" class="check-label"><input v-model="withBasis" type="checkbox" />Указать документ-основание</label>
            <BasisDocumentForm v-if="withBasis && session.can('documents.upload')" ref="basisForm" :department-id="departmentId" :busy="saving" />
            <p v-else class="muted compact">Сохранится черновик без основания. До приёмки основание добавляется отдельным уточнением.</p>
          </section>
        </fieldset>
        <div class="button-row intake-save-bar">
          <button class="button-primary" :disabled="saving || !receivedAt || !departmentId">{{ saving ? 'Сохранение…' : 'Сохранить поступление' }}</button>
          <button type="button" :disabled="saving" @click="back">Отмена</button>
        </div>
      </form>
    </template>
  </div>
</template>

<style scoped src="/src/modules/intake/intake-compact.css"></style>
