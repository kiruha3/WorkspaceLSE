<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import { emptyIssueOptions, issueStateLabels, type IssueOptions, type IssuePackage, type MaterialPackage } from '../../api/issuance'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import IssuePackageDraft from './IssuePackageDraft.vue'
import IssueActions from './IssueActions.vue'
import IssueFiles from './IssueFiles.vue'
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter(), requests = new LatestRequest(), optionsRequests = new LatestRequest()
const value = ref<IssuePackage | null>(null), material = ref<MaterialPackage | null>(null), options = ref<IssueOptions>(emptyIssueOptions()), loading = ref(false), optionsLoading = ref(false), error = ref<unknown>(null), optionsError = ref<unknown>(null), editing = ref(false), success = ref('')
const enabled = computed(() => session.issuanceEnabled && session.can('issue.view'))
const isNew = computed(() => route.path === '/issue-packages/new')
const materialId = computed(() => typeof route.query.material_id === 'string' ? route.query.material_id : '')
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/issue-packages(?:\?|$)/.test(route.query.return) ? route.query.return : '/issue-packages')
async function load() {
  if (!enabled.value) return
  loading.value = true; error.value = null
  try {
    if (isNew.value) {
      if (!materialId.value) throw new ApiError(400, 'material_required', 'Откройте подготовку комплекта из карточки нужной экспертизы.')
      await requests.run(signal => api.request<MaterialPackage>(`/materials/${materialId.value}/issue-packages/`, { signal }), result => { material.value = result; loading.value = false; if (result.package) { value.value = result.package; void router.replace(`/issue-packages/${result.package.id}`) } })
    } else await requests.run(signal => api.request<IssuePackage>(`/issue-packages/${route.params.id}/`, { signal }), result => { value.value = result; loading.value = false })
  } catch (cause) { error.value = cause; loading.value = false }
}
async function loadOptions() {
  if (!enabled.value) return
  optionsLoading.value = true; optionsError.value = null
  try { await optionsRequests.run(signal => api.request<IssueOptions>('/issue-packages/options/', { signal }), result => { options.value = result; optionsLoading.value = false }) }
  catch (cause) { optionsError.value = cause; optionsLoading.value = false }
}
async function initialize() { await load(); if (enabled.value) await loadOptions() }
function updated(result: IssuePackage) { requests.cancel(); loading.value = false; value.value = result; success.value = 'Сведения сохранены сервером.' }
function draftUpdated(result: IssuePackage) { editing.value = false; updated(result); if (isNew.value) void router.replace(`/issue-packages/${result.id}`) }
watch([() => route.params.id, materialId, enabled], () => { requests.cancel(); optionsRequests.cancel(); value.value = null; material.value = null; editing.value = false; success.value = ''; if (enabled.value) void initialize() }, { immediate: true })
onBeforeUnmount(() => { requests.cancel(); optionsRequests.cancel() })
</script>
<template>
  <p v-if="!enabled" class="state">Выдача недоступна в этой сессии.</p><template v-else><div class="page-heading"><div><p class="eyebrow">Полный комплект материала</p><h1>{{ value?.material.title || material?.material.title || 'Подготовка и выдача материалов' }}</h1><p class="muted">Состав, проверка и состоявшаяся передача фиксируются отдельно.</p></div><RouterLink data-back-to-issue-packages :to="returnTo">← К журналу выдачи</RouterLink></div><ApiMessage :error="error" /><ApiMessage :error="optionsError" /><p v-if="optionsLoading" class="state">Загрузка способов выдачи и видов документов…</p><button v-if="optionsError" data-retry-issue-options :disabled="optionsLoading" @click="loadOptions">Повторить загрузку справочников</button><p v-if="loading" class="state">Загрузка комплекта…</p><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <section v-if="isNew && material && !material.package" data-create-issue-package class="card"><IssuePackageDraft v-if="material.can_prepare" :material-id="material.material.id" :can-prepare="material.can_prepare" :options="options" @updated="draftUpdated" @cancel="router.push('/issue-packages')" /><p v-else class="message">Сервер не разрешил подготовку комплекта этого материала.</p></section>
    <template v-if="value && !isNew"><section class="card stack-card"><div class="section-heading"><h2>{{ value.material.title || 'Материал без названия' }}</h2><div class="button-row"><span data-package-state class="badge">{{ issueStateLabels[value.state] }}</span><button data-refresh-issue-package :disabled="loading" @click="load">Обновить серверные сведения</button><button v-if="value.allowed_actions.includes('issue.prepare') && !editing" data-edit-issue-package @click="editing = true">Подготовить / изменить состав</button></div></div><dl class="work-facts"><div><dt>Фактическая выдача</dt><dd data-issue-fact>{{ value.issuance ? value.issuance.issued_on : 'Не выдано — факт передачи не зафиксирован' }}</dd></div><div><dt>Версия комплекта</dt><dd>{{ value.version }}</dd></div><div><dt>Редакция состава</dt><dd>{{ value.content.number }}</dd></div><div><dt>Проверка текущего состава</dt><dd>{{ value.readiness.check_current ? 'Действует' : 'Не выполнена или устарела' }}</dd></div></dl><h3>Передаваемые материалы</h3><p class="issue-text">{{ value.content.materials_description || 'Описание материалов пока не указано' }}</p><p v-if="value.content.note">{{ value.content.note }}</p></section>
      <section v-if="value.readiness.warnings?.length" data-issue-warnings class="card stack-card"><h2>Документы и сведения нужно дополнить</h2><p class="muted">Эти напоминания не запрещают проверку и запись выдачи.</p><ul><li v-for="(item, index) in value.readiness.warnings" :key="`${item.code}-${index}`"><span v-if="item.expertise_id">{{ value.works.find(work => work.id === item.expertise_id)?.registration_number }} · </span>{{ item.message }}</li></ul></section>
      <section data-issue-readiness class="card stack-card"><h2>Проверка состояния</h2><ul v-if="value.readiness.blockers.length"><li v-for="(item, index) in value.readiness.blockers" :key="`${item.code}-${index}`"><span v-if="item.expertise_id">{{ value.works.find(work => work.id === item.expertise_id)?.registration_number }} · </span>{{ item.message }}</li></ul><p v-else class="muted">Препятствий по состоянию работ нет.</p><p class="muted compact">Проверка: {{ value.readiness.can_check ? 'разрешена по готовности' : 'пока недоступна' }} · Выдача: {{ value.readiness.can_issue ? 'разрешена по готовности' : 'пока недоступна' }}. Незавершённые работы, фактические реквизиты и права проверяются отдельно от полноты документов.</p></section>
      <section v-if="editing" class="card stack-card"><IssuePackageDraft :key="value.id" :package="value" :options="options" @updated="draftUpdated" @cancel="editing = false" /></section><IssueActions :key="`actions-${value.id}`" :package="value" :options="options" @updated="updated" />
      <section v-if="value.issuance" class="card stack-card"><h2>Подтверждённая выдача</h2><dl class="work-facts"><div><dt>Дата / способ</dt><dd>{{ value.issuance.issued_on }} · {{ value.issuance.method.name }}</dd></div><div><dt>Получатель</dt><dd>{{ value.issuance.recipient_name }}</dd></div><div><dt>Основание получения</dt><dd>{{ value.issuance.recipient_basis }}</dd></div><div><dt>Трек / идентификатор</dt><dd>{{ value.issuance.tracking || 'Не указан' }}</dd></div></dl><p>{{ value.issuance.comment }}</p><p>{{ value.issuance.reason }}</p><small>{{ value.issuance.actor?.full_name || 'Сотрудник не указан' }} · {{ value.issuance.created_at }}</small><BasisPreview v-if="value.issuance.evidence" :document="value.issuance.evidence" heading="Подтверждение выдачи" accepted-label="При выдаче подтверждена" /></section><IssueFiles :package="value" />
    </template>
  </template>
</template>
<style scoped>.issue-text { white-space: pre-wrap; overflow-wrap: anywhere; }</style>
