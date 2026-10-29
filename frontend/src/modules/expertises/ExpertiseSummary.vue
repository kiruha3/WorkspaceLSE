<script setup lang="ts">
import { computed } from 'vue'
import type { Expertise } from '../../api/types'

const props = defineProps<{ expertise: Expertise }>()
function date(value: string | null | undefined) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('.') : value || 'Неизвестно'
}
const facts = computed(() => {
  const work = props.expertise, history = work.historical && !work.historical.operational ? work.historical : null
  if (history) return [
    ['Исполнители в источнике', history.executor_raw || history.current_participants.map(item => item.full_name).join(', ') || 'В источнике не указаны'],
    ['Поступление', date(work.receipt.received_at)],
    [work.state === 'without_execution' ? 'Решение без исполнения по журналу' : 'Историческая дата окончания', date(work.state === 'without_execution' ? history.return_decided_on : history.completed_on)],
    ['Фактическая выдача в журнале', date(history.issued_on)],
  ]
  return [
    ['Текущие исполнители', work.current_assignments.map(item => item.employee.full_name).join(', ') || 'Назначений в АИС нет'],
    ['Поступление', date(work.receipt.received_at)],
    [work.closure ? work.closure.kind === 'completed' ? 'Дата окончания в АИС' : 'Решение без исполнения в АИС' : 'Календарные дни', work.closure ? date(work.closure.ended_on) : String(work.production.calendar_days ?? 'Неизвестно')],
    ['Действующий срок', date(work.production.current_due_on)],
  ]
})
</script>

<template>
  <dl data-card-summary class="case-summary">
    <div v-for="[label, value] in facts" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
  </dl>
</template>

<style scoped>
.case-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 0 0 12px; padding: 11px 4px; background: white; border: 1px solid var(--border); border-radius: 6px; }
.case-summary > div { min-width: 0; padding: 0 12px; border-right: 1px solid #e6ece4; }
.case-summary > div:last-child { border-right: 0; }
.case-summary dt { font-size: 11px; color: #66735f; line-height: 1.4; margin-bottom: 4px; }
.case-summary dd { margin: 0; font-size: 13px; font-weight: 600; line-height: 1.45; overflow-wrap: anywhere; }
@media (max-width: 1150px) { .case-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 0; } .case-summary > div:nth-child(2) { border-right: 0; } }
@media (max-width: 600px) { .case-summary { grid-template-columns: 1fr; padding: 10px 0; } .case-summary > div { border-right: 0; } }
</style>
