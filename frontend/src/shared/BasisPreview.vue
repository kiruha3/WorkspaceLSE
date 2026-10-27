<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { DocumentLink } from '../api/types'
const props = defineProps<{ document: DocumentLink; heading?: string; emptyText?: string; acceptedLabel?: string }>()
const kindLabels = { resolution: 'Постановление', decision: 'Определение', deadline_agreement: 'Подтверждение согласования срока', deadline_request: 'Запрос срока', expert_conclusion: 'Заключение эксперта', research_act: 'Акт исследования', sndz: 'СНДЗ', return_decision: 'Решение без исполнения', letter: 'Документ переписки', expert_subscription: 'Подписка эксперта', cover_letter: 'Сопроводительное', notification: 'Уведомление', invoice: 'Счёт' }
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
</script>
<template>
  <section class="document-preview">
    <h3>{{ heading || 'Документ-основание' }}</h3>
    <p v-if="!document && !props.document" class="muted">{{ emptyText || 'Основание пока не указано. До приёмки добавьте постановление или определение.' }}</p>
    <p v-else-if="!document" class="muted">Доступ к документу ограничен.</p>
    <template v-else>
      <p><strong>{{ document.title || kindLabels[document.kind] }}</strong> <span class="badge">{{ document.source_kind === 'paper_original' ? 'Бумажный оригинал' : 'Загруженная копия' }}</span></p>
      <p v-if="acceptedContext" class="muted compact">{{ accepted ? `${acceptedLabel || 'При окончании подтверждена'} версия ${accepted.number}. Последующие загрузки не изменяют это подтверждение.` : 'Подтверждённая версия файла не установлена; позднейшая загрузка не считается подтверждением.' }}</p>
      <label v-if="acceptedContext && !file && versions.length" class="version-select">Просмотреть другую версию<select v-model="selected"><option value="">Подтверждённая версия неизвестна</option><option v-for="item in versions" :key="item.id" :value="item.id">Версия {{ item.number }} · {{ item.original_name }}</option></select></label>
      <p v-if="acceptedContext && file && file.id !== document.accepted_version_id" data-unconfirmed-file class="message">{{ acceptedLabel ? 'Просматриваемая версия не подтверждена этим событием.' : 'Просматриваемая версия не подтверждена этим окончанием.' }}</p>
      <p v-if="!versions.length" class="muted compact">{{ document.source_kind === 'paper_original' ? 'Заявлено наличие бумажного оригинала. Электронный скан пока не добавлен.' : heading ? 'Копия ещё не сохранена. Необходимо загрузить файл.' : 'Копия ещё не сохранена. Для приёмки необходимо загрузить файл.' }}</p>
      <template v-if="file">
        <label v-if="versions.length > 1" class="version-select">Версия файла<select v-model="selected"><option v-for="item in versions" :key="item.id" :value="item.id">Версия {{ item.number }} · {{ item.original_name }}</option></select></label>
        <div class="document-meta"><span>{{ file.original_name }} · {{ Math.ceil(file.size / 1024) }} КБ · версия {{ file.number }}</span><a :href="file.download_url" download>Скачать оригинал</a></div>
        <template v-if="file.preview_url && !previewFailed">
          <img v-if="file.content_type.startsWith('image/')" class="document-image" :src="file.preview_url" :alt="file.original_name" @error="previewFailed = true" />
          <iframe v-else-if="file.content_type === 'application/pdf'" class="document-frame" :src="file.preview_url" :title="`Просмотр ${file.original_name}`" @error="previewFailed = true" />
          <p v-else class="muted compact">Предпросмотр этого формата недоступен. Скачайте оригинал.</p>
        </template>
        <p v-else class="muted compact">{{ previewFailed ? 'Не удалось загрузить предпросмотр. Повторите открытие карточки или скачайте оригинал.' : 'Предпросмотр недоступен. Скачайте оригинал.' }}</p>
      </template>
    </template>
  </section>
</template>
