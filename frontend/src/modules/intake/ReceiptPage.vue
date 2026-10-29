<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { BasisDocument, Expertise, FileVersion, Receipt, Reference } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
import BasisDocumentForm from '../../shared/BasisDocumentForm.vue'
import HelpTip from '../../shared/ui/HelpTip.vue'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
const api = useApi(), session = useSessionStore(), route = useRoute(), router = useRouter()
const receipt = ref<Receipt | null>(null), loading = ref(false), error = ref<unknown>(null), commandError = ref<unknown>(null), refsError = ref<unknown>(null), success = ref(''), busy = ref(false)
const details = new LatestRequest(), hints = new LatestRequest()
const departments = ref<Reference[]>([]), specialties = ref<Reference[]>([])
const number = ref(''), historical = ref(''), departmentId = ref(''), specialtyId = ref(''), nature = ref<'primary' | 'repeated' | 'additional'>('primary'), commission = ref(false)
const numberCategory = ref(''), fillingNumbers = ref(false)
const numberCategories = [{ code: '1', name: 'Уголовное дело' }, { code: '2', name: 'Гражданское дело' }, { code: '3', name: 'Арбитражное дело' }, { code: '4', name: 'КоАП' }, { code: '5', name: 'КУСП' }, { code: '6', name: 'Экспертное исследование / по заявлению' }]
const isComplex = ref(false)
interface ExtraWork { key: string; department_id: string; specialty_id: string; registration_number: string; historical_number: string; decree3214: boolean }
const extraWorks = ref<ExtraWork[]>([])
function addWork() { extraWorks.value.push({ key: newCommandKey(), department_id: departmentId.value, specialty_id: '', registration_number: '', historical_number: '', decree3214: false }) }
function constructionFor(id: string) { return ['16.1', '16.2'].includes(specialties.value.find(item => item.id === id)?.code ?? '') }
watch(isComplex, value => { if (value && !extraWorks.value.length) addWork(); if (!value) extraWorks.value = [] }, { flush: 'sync' })
const construction = ref(false)
const constructionEligible = computed(() => ['16.1', '16.2'].includes(specialties.value.find(item => item.id === specialtyId.value)?.code ?? ''))
watch(constructionEligible, eligible => { if (!eligible) construction.value = false }, { flush: 'sync' })
const hintYear = ref(''), lastNumber = ref<string | null>(null), nextSequence = ref<number | null>(null), hintLoading = ref(false), hintError = ref<unknown>(null), key = ref('')
function numberDepartment(id: string) { return departments.value.find(item => item.id === id)?.code ?? '' }
function suggestedNumber(id: string, offset = 0) {
  const code = numberDepartment(id)
  const year = String(hintYear.value)
  return nextSequence.value !== null && /^[1-9]\d*$/.test(code) && /^20\d{2}$/.test(year)
    ? `${nextSequence.value + offset}/${code}-${numberCategory.value || '…'}-${year.slice(-2)}`
    : 'N/отдел-категория-ГГ'
}
const currentNumberPlaceholder = computed(() => suggestedNumber(departmentId.value))
const canFillNumbers = computed(() => /^[1-6]$/.test(numberCategory.value) && /^20\d{2}$/.test(String(hintYear.value)) && [departmentId.value, ...(isComplex.value ? extraWorks.value.map(row => row.department_id) : [])].every(id => /^[1-9]\d*$/.test(numberDepartment(id))))
function numberFillContext() { return JSON.stringify([receipt.value?.id, departmentId.value, numberCategory.value, String(hintYear.value), isComplex.value, extraWorks.value.map(row => [row.key, row.department_id])]) }
async function fillNumbers() {
  if (busy.value || fillingNumbers.value || !canFillNumbers.value) return
  const context = numberFillContext()
  fillingNumbers.value = true
  try {
    await hint()
    if (hintError.value || nextSequence.value === null || context !== numberFillContext()) return
    number.value = suggestedNumber(departmentId.value)
    if (isComplex.value) extraWorks.value.forEach((row, index) => { row.registration_number = suggestedNumber(row.department_id, index + 1) })
  } finally { fillingNumbers.value = false }
}
const amending = ref(false), amendDate = ref(''), amendSender = ref(''), amendDepartment = ref(''), amendReason = ref(''), replaceBasis = ref(false), basisForm = ref<InstanceType<typeof BasisDocumentForm> | null>(null)
const uploadFile = ref<File | null>(null), uploadedFile = ref<File | null>(null), uploadError = ref<unknown>(null)
let uploadAttempt: { key: string; documentId: string; expectedVersion: number; file: File } | null = null
const canRegister = computed(() => session.can('expertise.register') && receipt.value?.status === 'accepted')
const document = computed(() => receipt.value?.basis_document && !('restricted' in receipt.value.basis_document) ? receipt.value.basis_document : null)
const basisReady = computed(() => receipt.value?.basis_document && (!document.value || document.value.source_kind === 'paper_original' || document.value.versions.length > 0))
const primaryRow = computed(() => ({ registration_number: number.value.trim(), historical_number: historical.value.trim(), department_id: departmentId.value, specialty_id: specialtyId.value, appointment_nature: nature.value, is_commission: commission.value, ...(constructionEligible.value ? { decree3214: construction.value } : {}) }))
const registrationPayload = computed(() => isComplex.value
  ? { expected_version: receipt.value?.version, works: [primaryRow.value, ...extraWorks.value.map(row => ({ registration_number: row.registration_number.trim(), historical_number: row.historical_number.trim(), department_id: row.department_id, specialty_id: row.specialty_id, appointment_nature: nature.value, is_commission: commission.value, ...(constructionFor(row.specialty_id) ? { decree3214: row.decree3214 } : {}) }))] }
  : { expected_version: receipt.value?.version, ...primaryRow.value, complex_group_id: null })
const registrationReady = computed(() => Boolean(number.value.trim() && departmentId.value && specialtyId.value && (!isComplex.value || (extraWorks.value.length && extraWorks.value.every(row => row.registration_number.trim() && row.department_id && row.specialty_id)))))
interface SequenceWarning { stamp: string; year: number; rows: { index: number; entered: string; expected: string }[] }
const sequenceWarning = ref<SequenceWarning | null>(null), registrationForm = ref<HTMLFormElement | null>(null), sequenceWarningPanel = ref<HTMLElement | null>(null)
let sequenceCheckedStamp = ''
async function inspectNumberSequence() {
  const values = [number.value.trim(), ...(isComplex.value ? extraWorks.value.map(row => row.registration_number.trim()) : [])]
  const parsed = values.map((entered, index) => {
    const match = /^([1-9]\d{0,8})\/([1-9]\d*)-([1-6])-(\d{2})$/.exec(entered)
    return match ? { index, entered, sequence: Number(match[1]), suffix: `/${match[2]}-${match[3]}-${match[4]}`, year: 2000 + Number(match[4]), category: match[3] } : null
  }).filter((value): value is NonNullable<typeof value> => value !== null)
  // Leave malformed or mixed-year/category packets to the existing server validation.
  if (parsed.length !== values.length || new Set(parsed.map(row => `${row.year}:${row.category}`)).size !== 1) return null
  const checked = await api.request<{ next_sequence: number }>(`/expertises/number-hint/?${new URLSearchParams({ department_id: departmentId.value, year: String(parsed[0]!.year) })}`)
  if (!Number.isSafeInteger(checked.next_sequence) || checked.next_sequence < 1) throw new ApiError(502, 'invalid_response', 'Не удалось проверить очередность номера. Повторите регистрацию.')
  const rows = parsed.filter((row, index) => row.sequence !== checked.next_sequence + index).map(row => ({ index: row.index, entered: row.entered, expected: `${checked.next_sequence + row.index}${row.suffix}` }))
  return rows.length ? { year: parsed[0]!.year, rows } : null
}
async function editSequence() {
  const index = sequenceWarning.value?.rows[0]?.index ?? 0
  sequenceWarning.value = null; sequenceCheckedStamp = ''
  await nextTick()
  registrationForm.value?.querySelectorAll<HTMLInputElement>('input[name="registration_number"],input[name="additional_registration_number"]')[index]?.focus()
}
const registered = ref(false)
const amendmentDirty = computed(() => Boolean(amendReason.value || basisForm.value?.dirty) || (amending.value && (amendDate.value !== receipt.value?.received_at || amendSender.value !== receipt.value?.sender_name || amendDepartment.value !== (receipt.value?.department_id ?? ''))))
const dirty = computed(() => !registered.value && (Boolean(number.value || numberCategory.value || historical.value || specialtyId.value || construction.value || isComplex.value || commission.value || nature.value !== 'primary' || amendReason.value || uploadFile.value || basisForm.value?.dirty) || (amending.value && Boolean(amendDate.value !== receipt.value?.received_at || amendSender.value !== receipt.value?.sender_name || amendDepartment.value !== (receipt.value?.department_id ?? '')))))
useDirtyGuard(() => dirty.value, router, () => busy.value || fillingNumbers.value)
watch(() => JSON.stringify(registrationPayload.value), () => { key.value = ''; sequenceWarning.value = null; sequenceCheckedStamp = '' }, { flush: 'sync' })
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/intake(?:\?|$)/.test(route.query.return) ? route.query.return : '/intake')
async function load() {
  loading.value = true; error.value = null
  try {
    await details.run(signal => api.request<Receipt>(`/receipts/${route.params.id}/`, { signal }), value => {
      receipt.value = value; loading.value = false
      if (!departmentId.value) departmentId.value = value.department_id ?? ''
      if (!hintYear.value) hintYear.value = value.received_at.slice(0, 4)
      if (!amending.value) { amendDate.value = value.received_at; amendSender.value = value.sender_name; amendDepartment.value = value.department_id ?? '' }
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
async function register(confirmed = false) {
  if (busy.value || fillingNumbers.value || !canRegister.value || !receipt.value || !registrationReady.value) return
  busy.value = true; commandError.value = null; success.value = ''
  try {
    const stamp = JSON.stringify(registrationPayload.value), receiptId = receipt.value.id
    if (confirmed) {
      if (sequenceWarning.value?.stamp !== stamp) return
      sequenceCheckedStamp = stamp; sequenceWarning.value = null
    } else if (sequenceCheckedStamp !== stamp) {
      const warning = await inspectNumberSequence()
      if (!registrationForm.value || receipt.value?.id !== receiptId || JSON.stringify(registrationPayload.value) !== stamp) return
      if (warning) {
        sequenceWarning.value = { stamp, ...warning }
        await nextTick(); sequenceWarningPanel.value?.focus()
        return
      }
      sequenceCheckedStamp = stamp
    }
    if (!key.value) key.value = newCommandKey()
    const result = await api.request<Expertise | { expertises: Expertise[] }>(`/receipts/${receipt.value.id}/${isComplex.value ? 'complex-expertises' : 'expertises'}/`, { method: 'POST', body: registrationPayload.value, headers: { 'Idempotency-Key': key.value } })
    const work = 'expertises' in result ? result.expertises[0]! : result
    registered.value = true; busy.value = false
    await router.push({ path: `/expertises/${work.id}`, query: { return: '/expertises' } })
  } catch (cause) {
    commandError.value = cause
    // A definite rejection can be checked again. An uncertain response must
    // replay the same command, which may already have consumed this number.
    if (cause instanceof ApiError && cause.status >= 400 && cause.status < 500) sequenceCheckedStamp = ''
  } finally { busy.value = false }
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
  hints.cancel(); receipt.value = null
  construction.value = false
  isComplex.value = false; extraWorks.value = []
  numberCategory.value = ''
  number.value = ''; historical.value = ''; departmentId.value = ''; specialtyId.value = ''; nature.value = 'primary'; commission.value = false; hintYear.value = ''; lastNumber.value = null; nextSequence.value = null
  amending.value = false; amendDate.value = ''; amendSender.value = ''; amendDepartment.value = ''; amendReason.value = ''; replaceBasis.value = false; uploadFile.value = null; uploadedFile.value = null; uploadAttempt = null; registered.value = false
  commandError.value = null; uploadError.value = null; success.value = ''; void load()
}, { immediate: true })
void loadReferences()
onBeforeUnmount(() => { details.cancel(); hints.cancel() })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">Поступление · материал</p><h1>{{ receipt?.material.title || 'Карточка поступления' }}</h1><p class="muted">{{ receipt ? `Поступление ${receipt.id.slice(0, 8)} · версия ${receipt.version}` : 'Загрузка серверных данных' }}</p></div><RouterLink :to="returnTo">← К поступлениям</RouterLink></div>
  <ApiMessage :error="error" /><p v-if="loading" class="state">Загрузка поступления…</p>
  <template v-if="receipt">
    <section class="card"><div class="section-heading"><h2>Сведения приёмки</h2><div class="button-row"><span class="badge" :class="receipt.status === 'accepted' ? 'badge-green' : 'badge-amber'">{{ receipt.status === 'historical' ? 'Историческое поступление' : receipt.status === 'accepted' ? 'Принято' : 'Черновик' }}</span><button :disabled="busy" @click="load">Обновить серверные сведения</button></div></div><dl class="profile-facts"><div><dt>Дата поступления</dt><dd>{{ receipt.received_at }}</dd></div><div><dt>Отправитель</dt><dd>{{ receipt.sender_name || 'Не указан' }}</dd></div><div><dt>Первоначальный отдел</dt><dd>{{ departments.find(item => item.id === receipt?.department_id)?.name || (receipt.department_id ? 'Указан' : 'Не указан') }}</dd></div></dl><ApiMessage :error="commandError" /><p v-if="success" class="message message-success" role="status">{{ success }}</p><div class="button-row"><button v-if="receipt.status === 'draft' && session.can('receipts.accept')" data-accept-receipt class="button-primary" :disabled="busy || !basisReady" @click="accept">Принять поступление</button><button v-if="receipt.status !== 'historical' && session.can('receipts.amend')" :disabled="busy" @click="toggleAmend">Редактировать поступление</button></div><p v-if="receipt.status === 'draft' && !basisReady" class="muted compact">Для приёмки необходимо основание: бумажный оригинал или сохранённая копия.</p>
      <form v-if="amending" class="inset-form form-grid" @submit.prevent="amend"><h3>Уточнение с основанием</h3><ApiMessage :error="refsError" /><fieldset class="form-grid" :disabled="busy"><div class="form-columns"><label>Дата поступления<input v-model="amendDate" type="date" required /></label><label>Отправитель<input v-model="amendSender" /></label><label>Первоначальный отдел<select v-model="amendDepartment" required><option value="">Выберите отдел</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label></div><label v-if="session.can('documents.upload')" class="check-label"><input v-model="replaceBasis" type="checkbox" />Добавить или заменить документ-основание</label><BasisDocumentForm v-if="replaceBasis" ref="basisForm" :department-id="amendDepartment" :busy="busy" /><label>Причина уточнения<textarea v-model="amendReason" name="amend_reason" required rows="2" /></label></fieldset><button class="button-primary align-start" :disabled="busy || !amendReason.trim()">Сохранить уточнение</button></form>
    </section>
    <section class="card stack-card"><BasisPreview :document="receipt.basis_document" /><form v-if="document && session.can('documents.upload')" class="inset-form form-grid" @submit.prevent="upload"><h4>Добавить скан / новую версию файла</h4><ApiMessage :error="uploadError" /><label>Файл<input type="file" :disabled="busy" @change="selectUpload" /></label><p class="muted compact">Общий документ сохраняет прежние версии. Новый файл будет доступен по разрешённым связям этого основания.</p><button class="align-start" :disabled="busy || !uploadFile">Сохранить новую версию</button></form></section>
    <section v-if="canRegister" class="card stack-card"><div class="section-heading"><div><p class="eyebrow">Самостоятельная команда</p><h2>{{ isComplex ? 'Регистрация комплексной экспертизы' : 'Закрепить номер экспертизы' }}</h2></div><span class="badge">Номер можно подставить или ввести вручную</span></div><p class="muted compact">Делопроизводитель регистрирует работу по специальности. Начальник отдела назначает конкретного эксперта отдельным действием.</p><ApiMessage :error="refsError" /><form ref="registrationForm" data-register-expertise class="form-grid" @submit.prevent="register()"><fieldset class="form-grid" :disabled="busy || fillingNumbers"><div class="button-row"><label class="check-label"><input v-model="isComplex" name="is_complex" type="checkbox" />Комплексная экспертиза</label><HelpTip label="Комплексная экспертиза">Укажите отдельный номер, специальность и отдел для каждой работы. Все строки сохраняются вместе. Постановление и материалы общие. Характер назначения и комиссионность ниже применяются ко всем строкам.</HelpTip></div><div class="number-fill-tools">
        <label>Категория дела<select v-model="numberCategory" name="number_category"><option value="">Выберите категорию</option><option v-for="item in numberCategories" :key="item.code" :value="item.code">{{item.code}} · {{item.name}}</option></select></label>
        <label>Год регистрации<input v-model="hintYear" type="number" min="2000" max="2099" name="hint_year" /></label>
        <div class="button-row"><button type="button" data-fill-registration-number :disabled="busy || fillingNumbers || !canFillNumbers" @click="fillNumbers">{{fillingNumbers?'Подбор номера…':isComplex?'Подставить номера':'Подставить номер'}}</button><HelpTip label="Подставить номер">Запрашивает свежий максимальный номер учреждения за выбранный год. Для комплекса подставляет последовательные номера с отделом каждой строки и общей категорией. Введённые номера заменяются только по нажатию этой кнопки. Номера сохраняются и проверяются при регистрации.</HelpTip></div>
      </div><ApiMessage :error="hintError" /><h3 v-if="isComplex">Специальность 1</h3><div class="form-columns"><label>Отдел работы<select v-model="departmentId" name="department_id" required><option value="">Выберите отдел</option><option v-for="item in departments.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Специальность<select v-model="specialtyId" name="specialty_id" required><option value="">Выберите специальность</option><option v-for="item in specialties.filter(item => item.is_active)" :key="item.id" :value="item.id">{{ item.code }} · {{ item.name }}</option></select></label><label>Текущий номер<input v-model="number" name="registration_number" :placeholder="currentNumberPlaceholder" required pattern="[0-9]+/[0-9]+-[1-6]-[0-9]{2}" /><small>Формат N/отдел-категория-год. Категорию можно выбрать выше или указать в номере. Исторический номер — отдельно.</small></label><label>Исторический номер, если известен<input v-model="historical" name="historical_number" /></label></div><label v-if="constructionEligible" class="check-label"><input v-model="construction" name="decree3214" type="checkbox" />Самовольное строение <small>Учитывать в графе3214-р. Дополнительный файл не обязателен.</small></label><section v-if="isComplex" class="form-grid" data-complex-registration>
        <article v-for="(row,index) in extraWorks" :key="row.key" class="inset-form form-grid" data-complex-row>
          <div class="section-heading"><h3>Специальность {{index+2}}</h3><button v-if="extraWorks.length>1" type="button" data-remove-complex-row @click="extraWorks.splice(index,1)">Убрать строку</button></div>
          <div class="form-columns">
            <label>Отдел работы<select v-model="row.department_id" name="additional_department_id" required><option value="">Выберите отдел</option><option v-for="item in departments.filter(item=>item.is_active)" :key="item.id" :value="item.id">{{item.code}} · {{item.name}}</option></select></label>
            <label>Специальность<select v-model="row.specialty_id" name="additional_specialty_id" required @change="row.decree3214=false"><option value="">Выберите специальность</option><option v-for="item in specialties.filter(item=>item.is_active)" :key="item.id" :value="item.id">{{item.code}} · {{item.name}}</option></select></label>
            <label>Текущий номер<input v-model="row.registration_number" name="additional_registration_number" :placeholder="suggestedNumber(row.department_id,index+1)" required pattern="[0-9]+/[0-9]+-[1-6]-[0-9]{2}" /></label>
            <label>Исторический номер, если известен<input v-model="row.historical_number" name="additional_historical_number" /></label>
          </div>
          <label v-if="constructionFor(row.specialty_id)" class="check-label"><input v-model="row.decree3214" name="additional_decree3214" type="checkbox" />Самовольное строение · 3214-р</label>
        </article>
        <button type="button" data-add-complex-row class="align-start" @click="addWork">+ Добавить специальность</button>
      </section><div class="number-hint"><div><p v-if="hintLoading" class="muted compact">Загрузка последнего номера…</p><template v-else><p class="compact">Максимальный номер по учреждению за {{ hintYear }}: <strong>{{ lastNumber || 'не найден' }}</strong></p><p v-if="nextSequence !== null" data-next-sequence class="compact">Следующий порядковый номер: <strong>{{ nextSequence }}</strong></p></template><p class="muted compact">Первая часть номера общая для всех отделов и категорий за год. Номер закрепляется при регистрации.</p></div></div><div class="form-columns"><label>Характер назначения<select v-model="nature" name="appointment_nature"><option value="primary">Первичная</option><option value="repeated">Повторная</option><option value="additional">Дополнительная</option></select></label><label class="check-label"><input v-model="commission" name="is_commission" type="checkbox" />Комиссионная: один номер, не менее двух квалифицированных участников</label></div></fieldset><section v-if="sequenceWarning" ref="sequenceWarningPanel" data-sequence-warning class="message sequence-warning" role="alert" tabindex="-1">
        <h3>{{isComplex?'Номера не по порядку':'Номер не по порядку'}}</h3>
        <p>Проверьте очередность за {{sequenceWarning.year}} год. Вы уверены, что хотите зарегистрировать {{isComplex?'указанные номера':'указанный номер'}}?</p>
        <table><thead><tr><th>Указано</th><th>По порядку</th></tr></thead><tbody><tr v-for="row in sequenceWarning.rows" :key="row.index"><td>{{row.entered}}</td><td>{{row.expected}}</td></tr></tbody></table>
        <div class="button-row"><button type="button" data-edit-sequence :disabled="busy" @click="editSequence">{{isComplex?'Исправить номера':'Исправить номер'}}</button><button type="button" data-confirm-sequence class="button-primary" :disabled="busy" @click="register(true)">Да, зарегистрировать</button></div>
      </section><button v-else class="button-primary align-start" :disabled="busy || fillingNumbers || !registrationReady">{{ busy ? 'Сохранение…' : isComplex ? 'Зарегистрировать все номера' : 'Закрепить номер' }}</button></form></section>
    <p v-else-if="receipt.status === 'draft' && session.can('expertise.register')" class="message message-error stack-card">Номер можно закрепить после приёмки поступления.</p>
  </template>
</template>

<style scoped>
.sequence-warning{background:#fff9ed;border:1px solid #d8b369;color:var(--ink)}
.sequence-warning:focus{outline:2px solid #bd8a30;outline-offset:2px}
.number-fill-tools{display:grid;grid-template-columns:minmax(0,1fr) 130px auto;align-items:end;gap:12px}
@media(max-width:720px){.number-fill-tools{grid-template-columns:1fr}}
</style>
