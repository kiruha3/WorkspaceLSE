<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { BasisDocument, ComplexGroup, Expertise, FileVersion, Receipt, Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter()
const receipt = ref<Receipt | null>(null), loading = ref(false), error = ref<unknown>(null), commandError = ref<unknown>(null), refsError = ref<unknown>(null), success = ref(''), busy = ref(false)
const details = new LatestRequest(), hints = new LatestRequest(), groupRequests = new LatestRequest()
const departments = ref<Reference[]>([]), specialties = ref<Reference[]>([]), groups = ref<ComplexGroup[]>([])
const number = ref(''), historical = ref(''), departmentId = ref(''), specialtyId = ref(''), nature = ref<'primary' | 'repeated' | 'additional'>('primary'), commission = ref(false), groupId = ref(''), groupTitle = ref('')
const construction = ref(false)
const constructionEligible = computed(() => ['16.1', '16.2'].includes(specialties.value.find(item => item.id === specialtyId.value)?.code ?? ''))
watch(constructionEligible, eligible => { if (!eligible) construction.value = false }, { flush: 'sync' })
const hintYear = ref(''), lastNumber = ref<string | null>(null), nextSequence = ref<number | null>(null), hintLoading = ref(false), hintError = ref<unknown>(null), key = ref('')
const amending = ref(false), amendDate = ref(''), amendSender = ref(''), amendDepartment = ref(''), amendReason = ref(''), replaceBasis = ref(false), basisForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const uploadFile = ref<File | null>(null), uploadedFile = ref<File | null>(null), uploadError = ref<unknown>(null)
let uploadAttempt: { key: string; documentId: string; expectedVersion: number; file: File } | null = null
const canRegister = computed(() => session.can('expertise.register') && receipt.value?.status === 'accepted')
const document = computed(() => receipt.value?.basis_document && !('restricted' in receipt.value.basis_document) ? receipt.value.basis_document : null)
const basisReady = computed(() => receipt.value?.basis_document && (!document.value || document.value.source_kind === 'paper_original' || document.value.versions.length > 0))
const registrationPayload = computed(() => ({ expected_version: receipt.value?.version, registration_number: number.value.trim(), historical_number: historical.value.trim(), department_id: departmentId.value, specialty_id: specialtyId.value, appointment_nature: nature.value, is_commission: commission.value, complex_group_id: groupId.value || null, ...(constructionEligible.value ? { decree3214: construction.value } : {}) }))
const registered = ref(false)
const amendmentDirty = computed(() => Boolean(amendReason.value || basisForm.value?.dirty) || (amending.value && (amendDate.value !== receipt.value?.received_at || amendSender.value !== receipt.value?.sender_name || amendDepartment.value !== (receipt.value?.department_id ?? ''))))
const dirty = computed(() => !registered.value && (Boolean(number.value || historical.value || specialtyId.value || construction.value || groupTitle.value || groupId.value || commission.value || nature.value !== 'primary' || amendReason.value || uploadFile.value || basisForm.value?.dirty) || (amending.value && Boolean(amendDate.value !== receipt.value?.received_at || amendSender.value !== receipt.value?.sender_name || amendDepartment.value !== (receipt.value?.department_id ?? '')))))
useDirtyGuard(() => dirty.value || busy.value, router)
watch(() => JSON.stringify(registrationPayload.value), () => { key.value = '' }, { flush: 'sync' })
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/intake(?:\?|$)/.test(route.query.return) ? route.query.return : '/intake')
async function load() {
  loading.value = true; error.value = null
  try {
    await details.run(signal => api.request<Receipt>(`/receipts/${route.params.id}/`, { signal }), value => {
      receipt.value = value; loading.value = false
      if (!departmentId.value) departmentId.value = value.department_id ?? ''
      if (!hintYear.value) hintYear.value = value.received_at.slice(0, 4)
      if (!amending.value) { amendDate.value = value.received_at; amendSender.value = value.sender_name; amendDepartment.value = value.department_id ?? '' }
      void loadGroups()
    })
  } catch (cause) { error.value = cause; loading.value = false }
}
async function loadReferences() {
  if (!session.canAny('expertise.register', 'receipts.amend')) return
  try {
    departments.value = await api.allPages<Reference>('/references/departments/')
    if (session.can('expertise.register')) specialties.value = await api.allPages<Reference>('/references/specialties/')
  } catch (cause) { refsError.value = cause }
}
async function loadGroups() {
  if (!canRegister.value) return
  try { await groupRequests.run(signal => api.allPages<ComplexGroup>(`/complex-groups/?receipt_id=${encodeURIComponent(String(route.params.id))}`, signal), value => { groups.value = value }) } catch (cause) { refsError.value = cause }
}
async function hint() {
  hints.cancel(); lastNumber.value = null; nextSequence.value = null; hintError.value = null; hintLoading.value = false
  if (!canRegister.value || !departmentId.value || !/^\d{4}$/.test(hintYear.value)) return
  hintLoading.value = true
  try { await hints.run(signal => api.request<{ last_number: string | null; next_sequence: number }>(`/expertises/number-hint/?${new URLSearchParams({ department_id: departmentId.value, year: hintYear.value })}`, { signal }), value => { lastNumber.value = value.last_number; nextSequence.value = value.next_sequence ?? null; hintLoading.value = false }) }
  catch (cause) { hintError.value = cause; hintLoading.value = false }
}
async function accept() {
  if (busy.value || !receipt.value || !session.can('receipts.accept')) return
  busy.value = true; commandError.value = null; success.value = ''
  try { receipt.value = await api.request<Receipt>(`/receipts/${receipt.value.id}/register/`, { method: 'POST', body: { expected_version: receipt.value.version } }); success.value = 'Поступление принято сервером. Номер экспертизы ещё не закреплён.' }
  catch (cause) { commandError.value = cause } finally { busy.value = false }
}
async function amend() {
  if (busy.value || !receipt.value || !session.can('receipts.amend')) return
  busy.value = true; commandError.value = null; success.value = ''
  try {
    const basis = replaceBasis.value ? await basisForm.value?.persist() : null
    receipt.value = await api.request<Receipt>(`/receipts/${receipt.value.id}/amend/`, { method: 'POST', body: { expected_version: receipt.value.version, reason: amendReason.value.trim(), received_at: amendDate.value, sender_name: amendSender.value.trim(), department_id: amendDepartment.value || null, ...(basis ? { basis_document_id: basis.id } : {}) } })
    amending.value = false; amendReason.value = ''; replaceBasis.value = false; success.value = 'Уточнение поступления сохранено сервером.'
  } catch (cause) { commandError.value = cause } finally { busy.value = false }
}
function toggleAmend() {
  if (amending.value && amendmentDirty.value && !window.confirm('Есть несохранённое уточнение поступления. Закрыть форму?')) return
  amending.value = !amending.value
  if (!amending.value) { amendReason.value = ''; replaceBasis.value = false }
}
async function register() {
  if (busy.value || !canRegister.value || !receipt.value) return
  busy.value = true; commandError.value = null; success.value = ''
  try {
    if (!key.value) key.value = newCommandKey()
    const result = await api.request<Expertise>(`/receipts/${receipt.value.id}/expertises/`, { method: 'POST', body: registrationPayload.value, headers: { 'Idempotency-Key': key.value } })
    registered.value = true; busy.value = false
    await router.push({ path: `/expertises/${result.id}`, query: { return: '/expertises' } })
  } catch (cause) { commandError.value = cause } finally { busy.value = false }
}
async function createGroup() {
  if (busy.value || !canRegister.value || !receipt.value) return
  busy.value = true; commandError.value = null
  try {
    const group = await api.request<ComplexGroup>('/complex-groups/', { method: 'POST', body: { receipt_id: receipt.value.id, title: groupTitle.value.trim() } })
    groups.value.push(group); groupId.value = group.id; groupTitle.value = ''; success.value = 'Комплексная группа создана. Каждая специальность регистрируется отдельно.'
  } catch (cause) { commandError.value = cause } finally { busy.value = false }
}
function selectUpload(event: Event) { uploadFile.value = (event.target as HTMLInputElement).files?.[0] ?? null }
async function upload() {
  if (busy.value || !document.value || !uploadFile.value || !session.can('documents.upload')) return
  busy.value = true; uploadError.value = null
  try {
    if (!uploadAttempt || uploadAttempt.file !== uploadFile.value || uploadAttempt.documentId !== document.value.id) {
      uploadAttempt = { key: newCommandKey(), documentId: document.value.id, expectedVersion: document.value.version, file: uploadFile.value }
      uploadedFile.value = null
    }
    if (uploadedFile.value !== uploadFile.value) {
      const body = new FormData(); body.append('expected_version', String(uploadAttempt.expectedVersion)); body.append('file', uploadFile.value)
      await api.request<FileVersion>(`/documents/${uploadAttempt.documentId}/versions/`, { method: 'POST', body, headers: { 'Idempotency-Key': uploadAttempt.key } }); uploadedFile.value = uploadFile.value
    }
    const updated = await api.request<BasisDocument>(`/documents/${document.value.id}/`)
    if (receipt.value) receipt.value = { ...receipt.value, basis_document: updated }
    uploadFile.value = null; uploadedFile.value = null; uploadAttempt = null; success.value = 'Новая версия файла сохранена сервером. Приёмка и регистрация выполняются отдельно.'
  } catch (cause) { uploadError.value = cause } finally { busy.value = false }
}
watch([departmentId, hintYear, canRegister], hint)
watch(() => route.params.id, () => {
  if (!route.path.startsWith('/receipts/')) return
  hints.cancel(); groupRequests.cancel(); receipt.value = null; groups.value = []
  construction.value = false
  number.value = ''; historical.value = ''; departmentId.value = ''; specialtyId.value = ''; nature.value = 'primary'; commission.value = false; groupId.value = ''; groupTitle.value = ''; hintYear.value = ''; lastNumber.value = null; nextSequence.value = null
  amending.value = false; amendDate.value = ''; amendSender.value = ''; amendDepartment.value = ''; amendReason.value = ''; replaceBasis.value = false; uploadFile.value = null; uploadedFile.value = null; uploadAttempt = null; registered.value = false
  commandError.value = null; uploadError.value = null; success.value = ''; void load()
}, { immediate: true })
void loadReferences()
onBeforeUnmount(() => { details.cancel(); hints.cancel(); groupRequests.cancel() })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Поступление · материал</p><h1>{{ receipt?.material.title || 'Карточка поступления' }}</h1><p class="muted">{{ receipt ? `Поступление ${receipt.id.slice(0, 8)} · версия ${receipt.version}` : 'Загрузка серверных данных' }}</p></div><RouterLink :to="returnTo">← К поступлениям</RouterLink></div>
  <ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка поступления…</p>
  <template v-if="receipt">
    <section class="card"><div class="section-heading"><h2>Сведения приёмки</h2><div class="button-row"><span class="badge" :class="receipt.status === 'accepted' ? 'badge-green' : 'badge-amber'">{{ receipt.status === 'historical' ? 'Историческое поступление' : receipt.status === 'accepted' ? 'Принято' : 'Черновик' }}</span><button :disabled="busy" @click="load">Обновить серверные сведения</button></div></div><dl class="profile-facts"><div><dt>Дата поступления</dt><dd>{{ receipt.received_at }}</dd></div><div><dt>Отправитель</dt><dd>{{ receipt.sender_name || 'Не указан' }}</dd></div><div><dt>Первоначальный отдел</dt><dd>{{ departments.find(item => item.id === receipt?.department_id)?.name || (receipt.department_id ? 'Указан' : 'Не указан') }}</dd></div></dl><ApiMessage :error="commandError" /><p v-if="success" class="message message-success" role="status">{{ success }}</p><div class="button-row"><button v-if="receipt.status === 'draft' && session.can('receipts.accept')" data-accept-receipt class="button-primary" :disabled="busy || !basisReady" @click="accept">Принять поступление</button><button v-if="receipt.status !== 'historical' && session.can('receipts.amend')" :disabled="busy" @click="toggleAmend">Редактировать поступление</button></div><p v-if="receipt.status === 'draft' && !basisReady" class="muted compact">Для приёмки необходимо основание: бумажный оригинал или сохранённая копия.</p>
      <form v-if="amending" class="inset-form form-grid" @submit.prevent="amend"><h3>Уточнение с основанием</h3><ApiMessage :error="refsError" /><fieldset class="form-grid" :disabled="busy"><div class="form-columns"><label>Дата поступления<input v-model="amendDate" type="date" required /></label><label>Отправитель<input v-model="amendSender" /></label><label>Первоначальный отдел<select v-model="amendDepartment" required><option value="">Выберите отдел</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label></div><label v-if="session.can('documents.upload')" class="check-label"><input v-model="replaceBasis" type="checkbox" />Добавить или заменить документ-основание</label><BasisDocumentForm v-if="replaceBasis" ref="basisForm" :department-id="amendDepartment" :busy="busy" /><label>Причина уточнения<textarea v-model="amendReason" name="amend_reason" required rows="2" /></label></fieldset><button class="button-primary align-start" :disabled="busy || !amendReason.trim()">Сохранить уточнение</button></form>
    </section>
    <section class="card stack-card"><BasisPreview :document="receipt.basis_document" /><form v-if="document && session.can('documents.upload')" class="inset-form form-grid" @submit.prevent="upload"><h4>Добавить скан / новую версию файла</h4><ApiMessage :error="uploadError" /><label>Файл<input type="file" :disabled="busy" @change="selectUpload" /></label><p class="muted compact">Общий документ сохраняет прежние версии. Новый файл будет доступен по разрешённым связям этого основания.</p><button class="align-start" :disabled="busy || !uploadFile">Сохранить новую версию</button></form></section>
    <section v-if="canRegister" class="card stack-card"><div class="section-heading"><div><p class="eyebrow">Самостоятельная команда</p><h2>Закрепить номер экспертизы</h2></div><span class="badge">Номер вводится вручную</span></div><p class="muted compact">Делопроизводитель регистрирует работу по специальности. Начальник отдела назначает конкретного эксперта отдельным действием.</p><ApiMessage :error="refsError" /><form data-register-expertise class="form-grid" @submit.prevent="register"><fieldset class="form-grid" :disabled="busy"><div class="form-columns"><label>Отдел работы<select v-model="departmentId" name="department_id" required><option value="">Выберите отдел</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Специальность<select v-model="specialtyId" name="specialty_id" required><option value="">Выберите специальность</option><option v-for="item in specialties.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Текущий номер<input v-model="number" name="registration_number" placeholder="151/4-1-26" required pattern="[0-9]+/[0-9]+-[1-6]-[0-9]{2}" /><small>Формат N/отдел-категория-год. Исторический номер сюда не включается.</small></label><label>Исторический номер, если известен<input v-model="historical" name="historical_number" /></label></div><label v-if="constructionEligible" class="check-label"><input v-model="construction" name="decree3214" type="checkbox" />Самовольное строение <small>Учитывать в графе3214-р. Дополнительный файл не обязателен.</small></label><div class="number-hint"><label>Год подсказки<input v-model="hintYear" type="number" min="2000" max="2099" name="hint_year" /></label><div><ApiMessage :error="hintError" /><p v-if="hintLoading" class="muted compact">Загрузка последнего номера…</p><template v-else><p class="compact">Максимальный номер по учреждению за {{ hintYear }}: <strong>{{ lastNumber || 'не найден' }}</strong></p><p v-if="nextSequence !== null" data-next-sequence class="compact">Следующий порядковый номер: <strong>{{ nextSequence }}</strong></p></template><p class="muted compact">Первая часть номера общая для всех отделов и категорий за год. Подсказка не резервирует номер и не заполняет поле.</p></div></div><p class="muted compact">Категории: 1 — уголовное; 2 — гражданское; 3 — арбитражное; 4 — КоАП; 5 — КУСП; 6 — исследование / по заявлению.</p><div class="form-columns"><label>Характер назначения<select v-model="nature" name="appointment_nature"><option value="primary">Первичная</option><option value="repeated">Повторная</option><option value="additional">Дополнительная</option></select></label><label class="check-label"><input v-model="commission" name="is_commission" type="checkbox" />Комиссионная: один номер, не менее двух квалифицированных участников</label></div><label>Комплексная группа, независимо от комиссионности<select v-model="groupId" name="complex_group_id"><option value="">Без комплексной группы</option><option v-for="group in groups" :key="group.id" :value="group.id">{{ group.title || group.id }}</option></select></label><p class="muted compact">В комплексе каждой специальности нужен отдельный номер. Второй эксперт той же специальности не создаёт новый номер.</p><div class="button-row"><label class="grow">Название новой комплексной группы<input v-model="groupTitle" name="complex_group_title" /></label><button type="button" @click="createGroup">Создать комплексную группу</button></div></fieldset><button class="button-primary align-start" :disabled="busy || !number.trim() || !departmentId || !specialtyId">{{ busy ? 'Сохранение…' : 'Закрепить номер' }}</button></form></section>
    <p v-else-if="receipt.status === 'draft' && session.can('expertise.register')" class="message message-error stack-card">Номер можно закрепить после приёмки поступления.</p>
  </template>
</template>
