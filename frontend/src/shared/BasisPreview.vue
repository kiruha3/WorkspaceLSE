<script setup lang="ts">
import HelpTip from './ui/HelpTip.vue'
import { computed, inject, ref, useId, watch } from 'vue'
import type { DocumentLink } from '../api/types'
import { compactPresentationKey } from './ui/compactPresentation'
const props = withDefaults(defineProps<{ document: DocumentLink; heading?: string; emptyText?: string; acceptedLabel?: string; compact?: boolean }>(), { compact: undefined })
const inheritedCompact = inject(compactPresentationKey, false)
const compact = computed(() => props.compact ?? inheritedCompact)
const detailsId = `document-details-${useId()}`, detailsOpen = ref(false), detailsRequested = ref(false)
function toggleDetails() {
  detailsOpen.value = !detailsOpen.value
  if (detailsOpen.value) detailsRequested.value = true
}
const kindLabels = { resolution: 'Постановление', decision: 'Определение', deadline_agreement: 'Подтверждение согласования срока', deadline_request: 'Запрос срока', expert_conclusion: 'Заключение эксперта', research_act: 'Акт исследования', sndz: 'СНДЗ', return_decision: 'Решение без исполнения', letter: 'Документ переписки', expert_subscription: 'Подписка эксперта', cover_letter: 'Сопроводительное', notification: 'Уведомление', invoice: 'Счёт',case_material:'Материалы дела / иные документы' }
const externalOpen=ref(false)
const selected = ref(''), previewFailed = ref(false)
const document = computed(() => props.document && !('restricted' in props.document) ? props.document : null)
const versions = computed(() => [...(document.value?.versions ?? [])].sort((a, b) => b.number - a.number))
const acceptedContext = computed(() => Boolean(document.value && 'accepted_version_id' in document.value))
const accepted = computed(() => versions.value.find(item => item.id === document.value?.accepted_version_id))
function defaultVersion() { return acceptedContext.value ? accepted.value?.id ?? '' : versions.value[0]?.id ?? '' }
watch(versions, value => { if (!value.some(item => item.id === selected.value)) selected.value = defaultVersion() }, { immediate: true })
watch([() => document.value?.id, () => document.value?.accepted_version_id], () => { selected.value = defaultVersion() })
const file = computed(() => versions.value.find(item => item.id === selected.value))
watch(() => file.value?.id, () => { previewFailed.value = false })
watch(()=>document.value?.id,()=>{externalOpen.value=false;detailsOpen.value=false;detailsRequested.value=false})
</script>
<template>
  <section class="document-preview" :class="{ 'document-preview-compact': compact }">
    <h3>{{ heading || 'Документ-основание' }}</h3>
    <p v-if="!document && !props.document" class="muted">{{ emptyText || 'Основание пока не указано. До приёмки добавьте постановление или определение.' }}</p>
    <p v-else-if="!document" class="muted">Доступ к документу ограничен.</p>
    <template v-else>
      <p><strong>{{ document.title || kindLabels[document.kind] }}</strong> <span class="badge">{{ document.source_kind === 'paper_original' ? 'Бумажный оригинал' : document.source_kind==='external_link'?'Внешняя ссылка':'Загруженная копия' }}</span></p>
      <p v-if="acceptedContext" class="muted compact">{{ accepted ? `${acceptedLabel || 'При окончании подтверждена'} версия ${accepted.number}. Последующие загрузки не изменяют это подтверждение.` : 'Подтверждённая версия файла не установлена; позднейшая загрузка не считается подтверждением.' }}</p>
      <label v-if="acceptedContext && !file && versions.length" class="version-select">Просмотреть другую версию<select v-model="selected"><option value="">Подтверждённая версия неизвестна</option><option v-for="item in versions" :key="item.id" :value="item.id">Версия {{ item.number }} · {{ item.original_name }}</option></select></label>
      <p v-if="acceptedContext && file && file.id !== document.accepted_version_id" data-unconfirmed-file class="message">{{ acceptedLabel ? 'Просматриваемая версия не подтверждена этим событием.' : 'Просматриваемая версия не подтверждена этим окончанием.' }}</p>
      <p v-if="!versions.length" class="muted compact">{{ document.source_kind === 'paper_original' ? 'Заявлено наличие бумажного оригинала. Электронный скан пока не добавлен.' : document.source_kind==='external_link'?'Сохранённой копии нет. Ссылка не считается принятым файлом или бумажным оригиналом.': heading ? 'Копия ещё не сохранена. Необходимо загрузить файл.' : 'Копия ещё не сохранена. Для приёмки необходимо загрузить файл.' }}</p>
      <template v-if="file">
        <label v-if="versions.length > 1" class="version-select">Версия файла<select v-model="selected"><option v-for="item in versions" :key="item.id" :value="item.id">Версия {{ item.number }} · {{ item.original_name }}</option></select></label>
        <div class="document-meta"><span>{{ file.original_name }} · {{ Math.ceil(file.size / 1024) }} КБ · версия {{ file.number }}</span><a :href="file.download_url" download>Скачать оригинал</a></div>
      </template>
      <button v-if="compact && (file || document.source_kind==='external_link'&&document.source_url)" data-document-details-toggle type="button" class="text-button document-details-toggle" :aria-expanded="detailsOpen" :aria-controls="detailsId" @click="toggleDetails">{{ detailsOpen ? 'Свернуть просмотр документа' : 'Открыть просмотр документа' }}</button>
      <div :id="detailsId" v-show="!compact || detailsOpen">
        <template v-if="!compact || detailsRequested">
          <section v-if="document.source_kind==='external_link'&&document.source_url" class="inset-form">
            <HelpTip label="Внешний источник">Внешний источник не загружается автоматически. Он может запрещать просмотр внутри системы. Изменения источника не изменяют сохранённые версии.</HelpTip>
            <div class="button-row"><a data-external-source :href="document.source_url" target="_blank" rel="noopener noreferrer">Открыть источник отдельно ↗</a><button v-if="!externalOpen" data-open-external-preview type="button" @click="externalOpen=true">Показать внешний источник</button><button v-else type="button" @click="externalOpen=false">Закрыть внешний просмотр</button></div>
            <iframe v-if="externalOpen" class="document-frame" :src="document.source_url" title="Внешний источник документа" sandbox="" referrerpolicy="no-referrer"/>
          </section>
          <template v-if="file">
            <template v-if="file.preview_url && !previewFailed">
              <img v-if="file.content_type.startsWith('image/')" class="document-image" :src="file.preview_url" :alt="file.original_name" @error="previewFailed = true" />
              <iframe v-else-if="file.content_type === 'application/pdf'" class="document-frame" :src="file.preview_url" :title="`Просмотр ${file.original_name}`" @error="previewFailed = true" />
              <p v-else class="muted compact">Предпросмотр этого формата недоступен. Скачайте оригинал.</p>
            </template>
            <p v-else class="muted compact">{{ previewFailed ? 'Не удалось загрузить предпросмотр. Повторите открытие карточки или скачайте оригинал.' : 'Предпросмотр недоступен. Скачайте оригинал.' }}</p>
          </template>
        </template>
      </div>
    </template>
  </section>
</template>

<style scoped>
.document-preview-compact h3 { margin-bottom: 7px; font-size: 14px; }
.document-preview-compact > p { font-size: 12px; overflow-wrap: anywhere; }
.document-preview-compact .document-meta { gap: 6px 12px; font-size: 12px; }
.document-details-toggle { margin-top: 8px; }
</style>
