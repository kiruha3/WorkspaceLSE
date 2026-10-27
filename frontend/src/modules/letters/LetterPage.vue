<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { LatestRequest, useApi } from '../../api/client'
import { emptyLetterOptions, letterStateLabels, replyLabels, type Letter, type LetterOptions } from '../../api/letters'
import { useSessionStore } from '../../stores/session'
import ApiMessage from '../../shared/ui/ApiMessage.vue'
import LetterDraftForm from './LetterDraftForm.vue'
import LetterActions from './LetterActions.vue'
import LetterAttachments from './LetterAttachments.vue'
import LetterHistory from './LetterHistory.vue'
const api = useApi(), session = useSessionStore(), route = useRoute(), requests = new LatestRequest(), optionsRequests = new LatestRequest()
const letter = ref<Letter | null>(null), options = ref<LetterOptions>(emptyLetterOptions()), loading = ref(false), error = ref<unknown>(null), optionsError = ref<unknown>(null), editing = ref(false), success = ref('')
const enabled = computed(() => session.correspondenceEnabled && session.can('letters.view'))
const returnTo = computed(() => typeof route.query.return === 'string' && /^\/letters(?:\?|$)/.test(route.query.return) ? route.query.return : '/letters')
const progress = { none: 'Ответов нет', registered: 'Ответ зарегистрирован', partial: 'Частичный ответ', final: 'Завершающий ответ' }
async function load() {
  if (!enabled.value) return
  loading.value = true; error.value = null
  try { await requests.run(signal => api.request<Letter>(`/letters/${route.params.id}/`, { signal }), value => { letter.value = value; loading.value = false }) }
  catch (cause) { error.value = cause; loading.value = false }
}
async function loadOptions() { try { await optionsRequests.run(signal => api.request<LetterOptions>('/letters/options/', { signal }), value => { options.value = value }) } catch (cause) { optionsError.value = cause } }
function updated(value: Letter) { requests.cancel(); loading.value = false; letter.value = value; success.value = 'Сведения сохранены сервером.' }
function draftUpdated(value: Letter) { editing.value = false; updated(value) }
watch([() => route.params.id, enabled], () => { requests.cancel(); optionsRequests.cancel(); if (enabled.value && route.path.startsWith('/letters/')) { letter.value = null; editing.value = false; success.value = ''; void load(); void loadOptions() } }, { immediate: true })
onBeforeUnmount(() => { requests.cancel(); optionsRequests.cancel() })
</script>
<template>
  <p v-if="!enabled" class="state">Переписка недоступна в этой сессии.</p>
  <template v-else><div class="page-heading"><div><p class="eyebrow">{{ letter?.direction === 'outgoing' ? 'Исходящее письмо' : 'Входящее письмо' }}</p><h1>{{ letter?.registration?.registration_number || letter?.content.subject || 'Карточка письма' }}</h1><p class="muted">Регистрация, получение, отправка, доставка и контроль сохраняются отдельными фактами.</p></div><RouterLink data-back-to-letters :to="returnTo">← К журналу переписки</RouterLink></div><ApiMessage :error="error" /><ApiMessage :error="optionsError" /><p v-if="loading" class="state">Загрузка письма…</p><p v-if="success" class="message message-success" role="status">{{ success }}</p>
    <template v-if="letter"><section class="card stack-card"><div class="section-heading"><h2>{{ letter.content.subject || 'Тема пока не указана' }}</h2><div class="button-row"><span data-letter-state class="badge">{{ letterStateLabels[letter.state] }}</span><button data-refresh-letter :disabled="loading" @click="load">Обновить серверные сведения</button><button v-if="letter.allowed_actions.includes('letters.draft') && !editing" data-edit-draft @click="editing = true">Редактировать черновик</button></div></div>
      <dl class="work-facts"><div><dt>Направление</dt><dd>{{ letter.direction === 'incoming' ? 'Входящее' : 'Исходящее' }}</dd></div><div><dt>Вид</dt><dd data-letter-kind>{{ letter.content.kind?.name || 'Не указан' }}</dd></div><div><dt>Ответственный</dt><dd>{{ letter.responsible?.full_name || 'Не указан' }}</dd></div><div><dt>Отдел</dt><dd>{{ letter.department?.name || 'Не указан' }}</dd></div><div><dt>Дата документа</dt><dd>{{ letter.content.document_on || 'Неизвестно' }}</dd></div><div><dt>Фактическое получение</dt><dd data-received-on>{{ letter.received_on || 'Неизвестно' }}</dd></div><div><dt>Внешний номер / дата</dt><dd>{{ letter.content.external_number || 'Неизвестен' }} · {{ letter.content.external_on || 'Неизвестна' }}</dd></div><div><dt>Отправитель</dt><dd>{{ letter.content.sender_name || 'Не указан' }}</dd></div><div><dt>Подтверждения доставки</dt><dd data-delivery-state>{{ letter.deliveries.length }} подтверждено</dd></div></dl><p class="letter-text">{{ letter.content.body || 'Содержание пока не указано' }}</p><p v-if="letter.content.note">{{ letter.content.note }}</p>
      <div v-if="letter.content.recipients.length"><h3>Адресаты</h3><p v-for="item in letter.content.recipients" :key="item.id">{{ item.name }} <span v-if="item.address">· {{ item.address }}</span> <span v-if="item.email">· {{ item.email }}</span></p></div>
      <p v-if="letter.content.material">Материал: {{ letter.content.material.title }}</p><p v-if="letter.content.expertises.length">Работы: <RouterLink v-for="work in letter.content.expertises" :key="work.id" :to="`/expertises/${work.id}`">{{ work.registration_number }} </RouterLink></p>
      <p v-if="letter.content.parent"><span v-if="'restricted' in letter.content.parent">Доступ к исходному письму ограничен.</span><RouterLink v-else :to="`/letters/${letter.content.parent.id}`">В ответ на {{ letter.content.parent.registration_number || letter.content.parent.subject }}</RouterLink><span v-if="letter.content.reply_completeness"> · {{ replyLabels[letter.content.reply_completeness] }} ответ</span></p><p class="muted compact">Версия записи {{ letter.version }} · редакция содержания {{ letter.content.number }}</p>
    </section>
    <section v-if="editing" class="card stack-card"><LetterDraftForm :key="letter.id" :letter="letter" :options="options" @updated="draftUpdated" @cancel="editing = false" /></section>
    <section class="card stack-card"><div class="section-heading"><h2>Ответы и контроль</h2><RouterLink v-if="letter.allowed_actions.includes('letters.reply')" data-create-reply :to="{ path: '/letters', query: { create: '1', parent_id: letter.id, direction: letter.direction === 'incoming' ? 'outgoing' : 'incoming' } }">Создать ответ</RouterLink></div><template v-if="letter.control"><dl class="work-facts"><div><dt>Контроль</dt><dd data-control-status>{{ letter.control.status === 'open' ? 'Открыт' : 'Закрыт' }}</dd></div><div><dt>Срок</dt><dd>{{ letter.control.due_on || 'Неизвестен' }} <span v-if="letter.control.overdue" class="badge badge-amber">Просрочен</span></dd></div><div><dt>Ход ответа</dt><dd>{{ progress[letter.control.response_progress] }}</dd></div></dl><p v-if="letter.control.due_basis">Основание срока: {{ letter.control.due_basis }}</p></template><p v-else data-control-status class="muted">{{ letter.allowed_actions.includes('control.view') ? 'На контроль не поставлено' : 'Сведения о контроле недоступны' }}</p><p class="muted compact">Ответы и их полнота не закрывают контроль автоматически.</p><p v-for="item in letter.replies" :key="item.id"><RouterLink :to="`/letters/${item.id}`">{{ item.registration_number || 'Черновик' }} · {{ item.subject || 'Без темы' }}</RouterLink> · {{ item.reply_completeness ? replyLabels[item.reply_completeness] : 'Полнота не указана' }} · {{ letterStateLabels[item.state] }}</p><p v-if="!letter.replies.length" class="muted">Доступных ответов нет.</p></section>
    <LetterActions :key="`actions-${letter.id}`" :letter="letter" :options="options" @updated="updated" /><LetterAttachments :key="`files-${letter.id}`" :letter="letter" @updated="updated" /><LetterHistory :letter="letter" />
    </template>
  </template>
</template>
<style scoped>.letter-text { white-space: pre-wrap; overflow-wrap: anywhere; }</style>
