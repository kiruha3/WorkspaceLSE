<script setup lang="ts">
import type { HistoricalWork } from '../../api/types'
defineProps<{ history: HistoricalWork }>()
const kinds = { expert_conclusion: 'Заключение эксперта', research_act: 'Акт экспертного исследования', sndz: 'Сообщение о невозможности дать заключение' }
const textFields = [
  ['authority_type', 'Тип органа'], ['authority_name', 'Назначивший орган'], ['official', 'Должностное лицо'],
  ['contact', 'Контакт'], ['basis_text', 'Основание в журнале'], ['case_description', 'Описание материалов'],
  ['inventory', 'Опись'], ['unresolved_note', 'Примечание к нерешённым вопросам'],
  ['unresolved_reason_raw', 'Причины в источнике'], ['notes', 'Отметки'], ['delivery', 'Выдача: текст источника'],
] as const
</script>
<template>
  <section data-historical-facts class="card stack-card">
    <div class="section-heading"><div><p class="eyebrow">Перенос журнала</p><h2>Исторические сведения</h2></div><span class="badge badge-amber">{{ history.operational ? 'Продолжение учёта подтверждено' : 'Нуждается в подтверждении для нового учёта' }}</span></div>
    <p class="muted compact">Сведения сохранены из источника. Перенос не подтверждает новый электронный комплект, допуск эксперта или фактическое назначение.</p>
    <dl class="work-facts">
      <div><dt>Результат в источнике</dt><dd>{{ history.result_kind ? kinds[history.result_kind] : 'Неизвестно' }}</dd></div>
      <div><dt>Окончание в журнале</dt><dd>{{ history.completed_on ?? 'Неизвестно' }}</dd></div>
      <div><dt>Решение без исполнения</dt><dd>{{ history.return_decided_on ?? 'Неизвестно' }}</dd></div>
      <div><dt>Фактическая выдача в журнале</dt><dd data-history-issued>{{ history.issued_on ?? 'Не подтверждена — дата отсутствует' }}</dd></div>
      <div><dt>Категория сложности</dt><dd data-history-complexity>{{ history.complexity_level ?? 'Неизвестно' }}</dd></div>
      <div><dt>Вопросов</dt><dd>{{ history.questions ?? 'Неизвестно' }}</dd></div>
      <div><dt>Категорических выводов</dt><dd>{{ history.categorical ?? 'Неизвестно' }}</dd></div>
      <div><dt>Вероятных выводов</dt><dd data-history-probable>{{ history.probable ?? 'Неизвестно' }}</dd></div>
      <div><dt>Нерешённых вопросов</dt><dd>{{ history.unresolved ?? 'Неизвестно' }}</dd></div>
      <div><dt>Сумма в источнике</dt><dd>{{ history.amount ?? 'Неизвестно' }}</dd></div>
    </dl>
    <p class="muted compact">{{ history.statistics_confirmed ? 'Полнота статистики вопросов подтверждена.' : 'Полнота статистики вопросов не подтверждена; пустое значение не равно нулю.' }}</p>
    <div class="subsection"><h3>Исполнители в источнике</h3><p>{{ history.executor_raw || 'В источнике не указаны' }}</p><p class="muted compact">Историческая связь, подтверждённая при сверке:</p><ul v-if="history.current_participants.length"><li v-for="employee in history.current_participants" :key="employee.id">{{ employee.full_name }}</li></ul><p v-else class="muted compact">Сотрудники ещё не сопоставлены.</p></div>
    <dl class="work-facts"><template v-for="[field, label] in textFields" :key="field"><div v-if="history[field]"><dt>{{ label }}</dt><dd class="preserve-lines">{{ history[field] }}</dd></div></template></dl>
    <div v-if="history.report_gaps.length" class="subsection"><h3>Что ещё уточнить</h3><ul><li v-for="gap in history.report_gaps" :key="gap.code">{{ gap.message }}</li></ul></div>
    <p class="muted compact">Строка источника {{ history.source.source_row }}<template v-if="history.source.source_observed_at"> · снимок {{ history.source.source_observed_at }}</template>.</p>
    <p v-if="history.source.origin_url" data-history-source-link class="muted compact">Источник, только чтение: {{ history.source.origin_url }}</p>
  </section>
</template>
