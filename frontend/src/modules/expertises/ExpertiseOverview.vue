<script setup lang="ts">
import { computed } from 'vue'
import type { Expertise } from '../../api/types'

const props = defineProps<{ expertise: Expertise }>()
const legacy = computed(() => props.expertise.historical && !props.expertise.historical.operational)
const kinds = { expert_conclusion: 'Заключение эксперта', research_act: 'Акт экспертного исследования', sndz: 'Сообщение о невозможности дать заключение' }
const natures = { primary: 'Первичная', repeated: 'Повторная', additional: 'Дополнительная' }
function date(value: string | null | undefined) {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('.') : value || 'Неизвестно'
}
const statistics = computed(() => legacy.value ? props.expertise.historical : props.expertise.result)
const resultLabel = computed(() => {
  const work = props.expertise, kind = legacy.value ? work.historical?.result_kind : work.result?.kind
  if (!kind) return 'Неизвестно'
  const accepted = work.closure?.kind === 'completed' && work.closure.result_id === work.result?.id
  return `${!legacy.value && !accepted ? 'Черновик · ' : ''}${kinds[kind]}`
})
const registration = computed(() => {
  const work = props.expertise
  return [
    [work.origin_kind === 'historical' ? 'Фактический отдел в журнале' : 'Отдел регистрации', `${work.department.code} · ${work.department.name}`],
    ['Специальность', work.specialty ? `${work.specialty.code} · ${work.specialty.name}` : 'Специальность не уточнена'],
    ['Характер назначения', work.appointment_nature ? natures[work.appointment_nature] : 'Характер назначения не уточнён'],
    ['Состав', work.is_commission === null ? 'Состав не уточнён' : work.is_commission ? 'Комиссионная · один номер' : 'Единоличная'],
    ['Категория / год', `${work.category_code} / ${work.year}`],
    ['Комплексная группа', work.complex_group?.title || (work.complex_group ? work.complex_group.id : work.historical && !work.historical.complex_known ? 'Не уточнена' : 'Не включена')],
  ]
})
const counters = computed(() => [
  ['complexity_level', 'Категория сложности', statistics.value?.complexity_level],
  ['questions', 'Вопросов', statistics.value?.questions],
  ['categorical', 'Категорических выводов', statistics.value?.categorical],
  ['probable', 'Вероятных выводов', statistics.value?.probable],
  ['unresolved', 'Нерешённых вопросов', statistics.value?.unresolved],
] as const)
const basis = computed(() => props.expertise.basis_document)
</script>

<template>
  <div class="overview-layout">
    <div class="overview-columns">
      <section class="overview-sheet">
        <h2>Регистрационные сведения</h2>
        <dl class="overview-facts"><div v-for="[label, value] in registration" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div></dl>
        <p v-if="expertise.complex_group" class="overview-note">В комплексной группе отдельный номер для каждой специальности. Доступ к этой работе не предоставляет доступ ко всем работам материала.</p>
        <p class="overview-version">Версия работы {{ expertise.version }}</p>
      </section>
      <section class="overview-sheet">
        <h2>{{ legacy ? 'Исторические сведения' : 'Результат в АИС' }}</h2>
        <dl class="overview-facts">
          <div><dt>{{ legacy ? 'Исторический результат' : 'Результат' }}</dt><dd data-overview-result>{{ resultLabel }}</dd></div>
          <div v-for="[key, label, value] in counters" :key="key"><dt>{{ label }}</dt><dd :data-overview-fact="key">{{ value ?? 'Неизвестно' }}</dd></div>
          <template v-if="legacy && expertise.historical">
            <div><dt>Решение без исполнения</dt><dd>{{ date(expertise.historical.return_decided_on) }}</dd></div>
            <div><dt>Сумма в источнике</dt><dd data-overview-fact="amount">{{ expertise.historical.amount ?? 'Неизвестно' }}</dd></div>
          </template>
        </dl>
        <p v-if="legacy" class="overview-note">Сведения журнала. Электронный комплект и назначения в АИС учитываются отдельно.</p>
      </section>
    </div>
    <div class="overview-secondary">
      <details>
        <summary><strong>Текущие исполнители</strong><span>{{ expertise.current_assignments.map(item => item.employee.full_name).join(', ') || 'Назначений в АИС нет' }}</span></summary>
        <p>Назначения, перепоручение и их история — в разделе «Исполнители». Исторические связи не заменяют назначение в АИС.</p>
      </details>
      <details>
        <summary><strong>Документ-основание</strong><span>{{ basis ? 'restricted' in basis ? 'Доступ к документу ограничен' : basis.title : 'Не указан' }}</span></summary>
        <p>Документ-основание и сведения о деле — в разделе «Дело». {{ basis ? '' : 'Для этой работы электронный документ-основание не указан.' }}</p>
      </details>
    </div>
  </div>
</template>

<style scoped>
.overview-layout { display: grid; gap: 22px; }
.overview-columns { display: grid; grid-template-columns: 1.05fr 1fr; gap: 20px; align-items: start; }
.overview-sheet { min-width: 0; padding: 24px; border: 1px solid var(--border); border-radius: 10px; background: white; }
.overview-sheet h2 { font-size: 20px; margin-bottom: 18px; }
.overview-facts { margin: 0; }
.overview-facts > div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; padding: 11px 0; border-bottom: 1px solid #edf0ea; }
.overview-facts > div:last-child { border-bottom: 0; }
.overview-facts dt { font-size: 13px; color: #59685f; }
.overview-facts dd { margin: 0; font-size: 14px; overflow-wrap: anywhere; }
.overview-version, .overview-note { margin-top: 18px; font-size: 12px; line-height: 1.6; color: #5a6a60; }
.overview-secondary { display: grid; gap: 12px; }
.overview-secondary details { background: white; border: 1px solid var(--border); border-radius: 8px; padding: 15px 20px; }
.overview-secondary summary { cursor: pointer; font-size: 13px; line-height: 1.7; }
.overview-secondary summary span { margin-left: 22px; color: #58695e; overflow-wrap: anywhere; }
.overview-secondary details > p { margin-top: 12px; color: #58695e; font-size: 13px; }
@media (max-width: 1150px) { .overview-columns { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .overview-sheet { padding: 18px; } .overview-facts > div { grid-template-columns: 1fr; gap: 5px; } .overview-secondary summary span { display: block; margin-left: 0; } }
</style>
