<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { routerKey } from 'vue-router'
import { ApiError, LatestRequest, useApi } from '../../api/client'
import { newCommandKey } from '../../api/commandKey'
import type { BasisDocument, DocumentKind, Expertise, ExpertiseCommandResponse, HistoryActivationPayload, Reference, ResultKind, ResultOptions } from '../../api/types'
import { useSessionStore } from '../../stores/session'
import { useDirtyGuard } from '../../shared/ui/useDirtyGuard'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import DocumentPicker from '../../shared/DocumentPicker.vue'
import BasisPreview from '../../shared/BasisPreview.vue'
const props = defineProps<{ expertise: Expertise }>(), emit = defineEmits<{ updated: [value: Expertise] }>()
const api = useApi(), session = useSessionStore(), requests = new LatestRequest()
const available = computed(() => session.journalApplicationEnabled && props.expertise.allowed_actions.includes('imports.history.activate') && session.can('imports.history.activate') && session.can('expertise.register'))
const editing = ref(false), busy = ref(false), saved = ref(false), uncertain = ref(false)
const error = ref<unknown>(null), optionsError = ref<unknown>(null), loadingOptions = ref(false)
const specialties = ref<Reference[]>([]), options = ref<ResultOptions | null>(null)
const nature = ref<'' | NonNullable<Expertise['appointment_nature']>>(''), commission = ref(''), complexConfirmed = ref(false), specialtyId = ref('')
const reason = ref(''), pausesComplete = ref(false), openPause = ref(''), pauses = ref<HistoryActivationPayload['past_suspensions']>([])
const basisMode = ref('existing'), basisId = ref(''), existingBasis = ref<BasisDocument | null>(null)
const resultMode = ref('existing'), resultId = ref(''), existingResult = ref<BasisDocument | null>(null)
const basisForm = ref<InstanceType<typeof DocumentPicker> | null>(null), resultForm = ref<InstanceType<typeof DocumentPicker> | null>(null)
const resultKind = ref<ResultKind | ''>(''), endDate = ref(''), complexity = ref(''), questions = ref(''), categorical = ref(''), probable = ref(''), unresolved = ref('')
const statistics = ref(false), sndzReason = ref(''), sndzComment = ref(''), returnReason = ref(''), comment = ref('')
const allocationsComplete=ref(false),allocations=ref<{reason_id:string;count:string;comment:string;document:BasisDocument|{id:string;restricted:true}|null}[]>([])
const attempt = ref<{ key: string; body: HistoryActivationPayload } | null>(null)
let active = true
const closed = computed(() => ['completed', 'without_execution'].includes(props.expertise.state)), isReturn = computed(() => props.expertise.state === 'without_execution')
const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Krasnoyarsk', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const resultKinds = computed<{ value: ResultKind; label: string }[]>(() => props.expertise.category_code === '6' ? [{ value: 'research_act', label: 'Акт экспертного исследования' }] : [{ value: 'expert_conclusion', label: 'Заключение эксперта' }, { value: 'sndz', label: 'Сообщение о невозможности дать заключение' }])
const evidenceKinds = computed<{ value: DocumentKind; label: string }[]>(() => isReturn.value ? [{ value: 'return_decision', label: 'Решение без исполнения' }] : resultKind.value ? [{ value: resultKind.value, label: resultKinds.value.find(item => item.value === resultKind.value)?.label || 'Итоговый документ' }] : [])
const stamp = computed(() => JSON.stringify([nature.value, commission.value, complexConfirmed.value, specialtyId.value, reason.value.trim(), pausesComplete.value, openPause.value, pauses.value, basisMode.value, basisId.value, resultMode.value, resultId.value, resultKind.value, endDate.value, complexity.value, questions.value, categorical.value, probable.value, unresolved.value, statistics.value, sndzReason.value, sndzComment.value, returnReason.value, comment.value,allocations.value,allocationsComplete.value]))
const original = ref('')
const confirmLeave = useDirtyGuard(() => editing.value && !saved.value && (stamp.value !== original.value || busy.value || Boolean(attempt.value) || Boolean(basisForm.value?.dirty || resultForm.value?.dirty)), inject(routerKey, undefined))
function invalidate() { attempt.value = null; uncertain.value = false; error.value = null }
watch(stamp, invalidate, { flush: 'sync' })
watch(basisId, value => { if (existingBasis.value?.id !== value.trim()) existingBasis.value = null }, { flush: 'sync' })
watch([resultId, resultKind], () => { existingResult.value = null }, { flush: 'sync' })
const valid = computed(() => {
  if (!editing.value || (!available.value && !uncertain.value) || !reason.value.trim()) return false
  if (uncertain.value && attempt.value) return true
  if (!nature.value || !commission.value || !complexConfirmed.value || !specialtyId.value || (basisMode.value === 'existing' && existingBasis.value?.id !== basisId.value.trim())) return false
  if (closed.value && resultMode.value === 'existing' && (!existingResult.value?.versions.length || existingResult.value.id !== resultId.value.trim() || existingResult.value.kind !== (isReturn.value ? 'return_decision' : resultKind.value))) return false
  const validDate = (value: string) => Boolean(value && value >= props.expertise.receipt.received_at && value <= today())
  if (props.expertise.state === 'suspended' && !validDate(openPause.value)) return false
  if (closed.value && (!validDate(endDate.value) || (!isReturn.value && !resultKind.value))) return false
  let previous = ''
  for (const pause of [...pauses.value].sort((a, b) => a.suspended_on.localeCompare(b.suspended_on))) {
    if (!validDate(pause.suspended_on) || !validDate(pause.resumed_on) || pause.resumed_on < pause.suspended_on || pause.suspended_on < previous || !pause.reason.trim()) return false
    previous = pause.resumed_on
  }
  return !(props.expertise.state === 'suspended' && openPause.value < previous) && !(closed.value && endDate.value < previous)
})
const conflict = computed(() => error.value instanceof ApiError && error.value.status === 409 && attempt.value && attempt.value.body.expected_version !== props.expertise.version)
async function loadOptions() {
  loadingOptions.value = true; optionsError.value = null
  try { await requests.run(async signal => ({ specialties: props.expertise.specialty ? [] : await api.allPages<Reference>('/references/specialties/', signal), options: closed.value ? await api.request<ResultOptions>(`/expertises/${props.expertise.id}/result-options/`, { signal }) : null }), value => { specialties.value = value.specialties; options.value = value.options; loadingOptions.value = false }) }
  catch (cause) { optionsError.value = cause; loadingOptions.value = false }
}
function start() {
  if (!available.value) return
  const history = props.expertise.historical!
  nature.value = props.expertise.appointment_nature ?? ''; commission.value = props.expertise.is_commission === null ? '' : props.expertise.is_commission ? 'yes' : 'no'
  complexConfirmed.value = false; specialtyId.value = props.expertise.specialty?.id ?? ''; reason.value = ''; pauses.value = []; pausesComplete.value = false; openPause.value = ''
  existingBasis.value = props.expertise.basis_document && !('restricted' in props.expertise.basis_document) ? props.expertise.basis_document : null
  basisId.value = existingBasis.value?.id ?? ''; basisMode.value = 'existing'
  resultKind.value = history.result_kind ?? ''; endDate.value = (isReturn.value ? history.return_decided_on : history.completed_on) ?? ''
  const numberText = (value: number | null) => value === null ? '' : String(value)
  complexity.value = numberText(history.complexity_level); questions.value = numberText(history.questions); categorical.value = numberText(history.categorical); probable.value = numberText(history.probable); unresolved.value = numberText(history.unresolved)
  const details=history.report_details
  statistics.value = history.statistics_confirmed; sndzReason.value = details?.sndz_reason?.id??''; sndzComment.value = details?.sndz_comment??''; returnReason.value = details?.return_reason?.id??''; comment.value = (isReturn.value?details?.return_comment:details?.note)??''
  allocationsComplete.value=details?.allocations_complete??false;allocations.value=(details?.unresolved_allocations??[]).map(item=>({reason_id:item.reason.id,count:String(item.count),comment:item.comment,document:item.document}))
  resultMode.value = 'existing'; resultId.value = ''; existingResult.value = null
  saved.value = false; editing.value = true; invalidate(); original.value = stamp.value; void loadOptions()
}
function selectBasis(value:BasisDocument|null){
 existingBasis.value=null
 if(value&&(!['resolution','decision'].includes(value.kind)||(value.source_kind==='uploaded_copy'&&!value.versions.length))){error.value=new ApiError(400,'basis_invalid','Нужно постановление или определение: оригинал либо сохранённая копия.');return}
 existingBasis.value=value
}
function selectResult(value:BasisDocument|null){
 existingResult.value=value&&value.kind===(isReturn.value?'return_decision':resultKind.value)&&value.versions.length?value:null
}
async function submit() {
  if (!valid.value || busy.value) return
  const workId = props.expertise.id
  busy.value = true; error.value = null
  try {
    if (!attempt.value) {
      const basis = basisMode.value === 'new' ? await basisForm.value?.persist() : existingBasis.value
      if (!basis) throw new ApiError(400, 'basis_required', 'Подтвердите документ-основание.')
      const resultDocument = closed.value ? resultMode.value === 'existing' ? existingResult.value : await resultForm.value?.persist() : null
      if (!active || workId !== props.expertise.id) return
      const body: HistoryActivationPayload = { expected_version: props.expertise.version, reason: reason.value.trim(), basis_document_id: basis.id, specialty_id: specialtyId.value,
        appointment_nature: nature.value as NonNullable<Expertise['appointment_nature']>, is_commission: commission.value === 'yes', complex_known: true, complex_group_id: props.expertise.complex_group?.id ?? null,
        suspension_history_complete: pausesComplete.value, past_suspensions: pauses.value.map(pause => ({ ...pause, reason: pause.reason.trim() })), suspended_on: props.expertise.state === 'suspended' ? openPause.value : null }
      if (closed.value) {
        if (!resultDocument?.versions.length) throw new ApiError(400, 'file_required', 'Подкрепите сохранённый файл итогового документа.')
        if (isReturn.value) body.return_data = { decided_on: endDate.value, document_id: resultDocument.id, return_reason_id: returnReason.value || null, comment: comment.value.trim() }
        else {
          const numeric = (value: string) => value === '' ? null : Number(value)
          body.result = { kind: resultKind.value as ResultKind, completed_on: endDate.value, document_id: resultDocument.id, complexity_level: numeric(complexity.value), questions: numeric(questions.value), categorical: numeric(categorical.value), probable: numeric(probable.value), unresolved: numeric(unresolved.value), statistics_complete: statistics.value,
            sndz_reason_id: resultKind.value === 'sndz' ? sndzReason.value || null : null, sndz_comment: resultKind.value === 'sndz' ? sndzComment.value.trim() : '', unresolved_allocations: allocations.value.map(item=>({reason_id:item.reason_id,count:Number(item.count),comment:item.comment.trim(),document_id:item.document?.id??null})), allocations_complete: allocationsComplete.value, note: comment.value.trim() }
        }
      }
      attempt.value = { key: newCommandKey(), body }
    }
    const response = await api.request<ExpertiseCommandResponse>(`/expertises/${workId}/activate-history/`, { method: 'POST', body: attempt.value.body, headers: { 'Idempotency-Key': attempt.value.key } })
    if (active && workId === props.expertise.id) { saved.value = true; editing.value = false; emit('updated', response.expertise) }
  } catch (cause) { if (active) { error.value = cause; uncertain.value = !(cause instanceof ApiError) || cause.status >= 500 || cause.code === 'invalid_response' } }
  finally { if (active) busy.value = false }
}
function cancel() { if (!busy.value && confirmLeave()) { editing.value = false; saved.value = true; invalidate() } }
onBeforeUnmount(() => { active = false; requests.cancel() })
</script>
<template>
  <section v-if="available || editing" data-history-confirmation class="card stack-card">
    <div class="section-heading"><div><p class="eyebrow">Переход к обычному процессу</p><h2>Подтвердить историческую работу</h2></div><button v-if="!editing && available" data-start-history @click="start">Подтвердить для нового учёта</button></div>
    <p class="muted compact">Источники сохраняются. Подтверждение не назначает эксперта и не подтверждает его специальность. Выданная работа этой командой не изменяется.</p>
    <form v-if="editing" data-history-form class="form-grid" @submit.prevent="submit">
      <ApiMessage :error="error" /><ApiMessage :error="optionsError" />
      <p v-if="uncertain" class="message">Ответ не получен. Повтор использует прежние документы, сведения, версию и ключ.</p>
      <p v-if="!available" class="message">Новое подтверждение больше не разрешено. Введённые данные сохранены.</p>
      <p v-if="conflict" class="message">Карточка обновлена; форма сохранена. <button data-adopt-history-version type="button" :disabled="busy || !available" @click="invalidate">Использовать версию {{ expertise.version }} для новой попытки</button></p>
      <fieldset class="form-grid" :disabled="busy || (!available && !uncertain)">
        <div class="form-columns"><label>Характер назначения<select v-model="nature" name="history_nature"><option value="">Не уточнён</option><option value="primary">Первичная</option><option value="repeated">Повторная</option><option value="additional">Дополнительная</option></select></label><label>Состав<select v-model="commission" name="history_commission"><option value="">Не уточнён</option><option value="no">Единоличная</option><option value="yes">Комиссионная</option></select></label><label v-if="!expertise.specialty">Подтверждённая специальность<select v-model="specialtyId" name="history_specialty"><option value="">Выберите специальность</option><option v-for="ref in specialties" :key="ref.id" :value="ref.id">{{ ref.code }} · {{ ref.name }}{{ ref.is_active ? '' : ' · историческая, неактивная' }}</option></select></label></div>
        <p v-if="expertise.specialty" class="muted compact">Специальность сохраняется: {{ expertise.specialty.code }} · {{ expertise.specialty.name }}.</p>
        <label class="check-label"><input v-model="complexConfirmed" name="history_complex_confirm" type="checkbox" />Подтверждаю: {{ expertise.complex_group ? `комплексная группа ${expertise.complex_group.title || expertise.complex_group.id}` : 'работа не входит в комплексную группу' }}</label>
        <DocumentPicker ref="basisForm" v-model="basisId" v-model:mode="basisMode" name="history_basis_id" :document="existingBasis" :department-id="expertise.department.id" :kinds="['resolution','decision']" :busy="busy" :input-locked="uncertain" required heading="Документ-основание" saved-note="Подтверждение работы сохраняется отдельно." @selected="selectBasis" @changed="invalidate"/>
        <h3>История приостановок</h3><label class="check-label"><input v-model="pausesComplete" name="history_suspensions_complete" type="checkbox" />Подтверждаю полноту истории приостановок</label><p class="muted compact">Если полнота неизвестна, дни без пауз останутся неизвестными. Пустой список не означает ноль приостановок.</p>
        <div v-for="(pause, index) in pauses" :key="index" class="form-columns"><label>Приостановлена<input v-model="pause.suspended_on" type="date" :min="expertise.receipt.received_at" :max="today()" required /></label><label>Возобновлена<input v-model="pause.resumed_on" type="date" :min="pause.suspended_on || expertise.receipt.received_at" :max="today()" required /></label><label>Основание интервала<input v-model="pause.reason" required /></label><button type="button" @click="pauses.splice(index,1)">Убрать интервал</button></div><button type="button" class="align-start" @click="pauses.push({suspended_on:'',resumed_on:'',reason:''})">Добавить подтверждённый интервал</button>
        <label v-if="expertise.state === 'suspended'">Начало текущей открытой приостановки<input v-model="openPause" name="history_open_pause" type="date" :min="expertise.receipt.received_at" :max="today()" required /></label>
        <template v-if="closed">
          <h3>{{ isReturn ? 'Подтвердить решение без исполнения' : 'Подтвердить фактический результат' }}</h3>
          <div class="form-columns"><label v-if="!isReturn">Вид результата<select v-model="resultKind" name="history_result_kind"><option value="">Выберите вид</option><option v-for="item in resultKinds" :key="item.value" :value="item.value">{{ item.label }}</option></select></label><label>{{ isReturn ? 'Дата решения' : 'Дата окончания' }}<input v-model="endDate" name="history_end_date" type="date" :min="expertise.receipt.received_at" :max="today()" required /></label></div>
          <template v-if="!isReturn"><div class="form-columns"><label>Сложность<input v-model="complexity" name="history_complexity" type="number" min="1" /></label><label>Q — вопросов<input v-model="questions" type="number" min="0" /></label><label>R — категорических<input v-model="categorical" type="number" min="0" /></label><label>S — вероятных<input v-model="probable" type="number" min="0" /></label><label>T — нерешённых<input v-model="unresolved" type="number" min="0" /></label></div><label class="check-label"><input v-model="statistics" type="checkbox" />Подтверждаю полноту статистики вопросов</label><label v-if="resultKind === 'sndz'">Причина СНДЗ<select v-model="sndzReason"><option value="">Пока не определена</option><option v-for="ref in options?.sndz_reasons ?? []" :key="ref.id" :value="ref.id">{{ ref.name }}</option></select></label><label v-if="resultKind === 'sndz'">Пояснение СНДЗ<textarea v-model="sndzComment" /></label></template>
          <label v-else>Причина решения<select v-model="returnReason"><option value="">Пока не определена</option><option v-for="ref in options?.return_reasons ?? []" :key="ref.id" :value="ref.id">{{ ref.name }}</option></select></label>
          <section v-if="!isReturn" class="subsection"><h4>Подтвердить причины нерешённых вопросов T</h4><p class="muted compact">Уточнённые сведения перенесены из истории. Проверьте их перед подтверждением нового учёта.</p>
            <div v-for="(item,index) in allocations" :key="index" class="inset-form form-grid"><div class="form-columns"><label>Причина<select v-model="item.reason_id" :name="`history_activation_allocation_reason_${index}`"><option value="">Выберите причину</option><option v-for="ref in options?.unresolved_reasons??[]" :key="ref.id" :value="ref.id">{{ref.name}}</option></select></label><label>Количество<input v-model="item.count" :name="`history_allocation_count_${index}`" type="number" min="1" step="1" required/></label></div><label>Пояснение<textarea v-model="item.comment" rows="2"/></label><template v-if="item.document"><BasisPreview :document="item.document" heading="Подтверждающий документ"/><button type="button" @click="item.document=null">Убрать ссылку на документ</button></template><button type="button" @click="allocations.splice(index,1)">Убрать причину</button></div>
            <button type="button" @click="allocations.push({reason_id:'',count:'',comment:'',document:null})">Добавить причину вопроса</button><label class="check-label"><input v-model="allocationsComplete" type="checkbox"/>Подтверждаю полное распределение T</label>
          </section>
          <label>Примечание к подтверждаемому итогу<textarea v-model="comment" /></label>
          <div v-if="evidenceKinds.length" data-history-result-document><DocumentPicker :key="isReturn?'return':resultKind" ref="resultForm" v-model="resultId" v-model:mode="resultMode" name="history_result_id" :document="existingResult" :department-id="expertise.department.id" :kinds="evidenceKinds.map(item=>item.value)" :kind-options="evidenceKinds" :require-file="true" required :busy="busy" :input-locked="uncertain" heading="Итоговый документ" saved-note="Подтверждение окончания выполняется отдельно." @selected="selectResult" @changed="invalidate"/></div>
          <p class="muted compact">Нужен сохранённый файл. Исходный текст журнала и история уточнений сохраняются.</p>
        </template>
        <label>Основание подтверждения<textarea v-model="reason" name="history_reason" required rows="2" /></label>
      </fieldset>
      <div class="button-row"><button data-confirm-history class="button-primary" :disabled="busy || loadingOptions || !valid">{{ busy ? 'Подтверждение…' : uncertain ? 'Повторить ту же попытку' : 'Подтвердить для нового учёта' }}</button><button type="button" :disabled="busy" @click="cancel">Отмена</button></div>
    </form>
  </section>
</template>
