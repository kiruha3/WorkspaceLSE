<script setup lang="ts">
import HelpTip from '../../shared/ui/HelpTip.vue'
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
        <HelpTip label="Комплексная группа" v-if="expertise.complex_group">В комплексной группе отдельный номер для каждой специальности. Доступ к этой работе не предоставляет доступ ко всем работам материала.</HelpTip>
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
        <HelpTip label="Исторические сведения" v-if="legacy">Сведения журнала. Электронный комплект и назначения в АИС учитываются отдельно.</HelpTip>
      </section>
    </div>
    <div class="overview-secondary">
      <div class="overview-context"><strong>Текущие исполнители</strong><span>{{ expertise.current_assignments.map(item => item.employee.full_name).join(', ') || 'Назначений в АИС нет' }}</span><HelpTip label="Текущие исполнители">Назначения, перепоручение и их история — в разделе «Исполнители». Исторические связи не заменяют назначение в АИС.</HelpTip></div>
      <div class="overview-context"><strong>Документ-основание</strong><span>{{ basis ? 'restricted' in basis ? 'Доступ к документу ограничен' : basis.title : 'Не указан' }}</span><HelpTip label="Документ-основание">Документ-основание и сведения о деле — в разделе «Дело».</HelpTip></div>
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
.overview-context { display:flex;align-items:center;gap:12px;background:white;border:1px solid var(--border);border-radius:8px;padding:12px 16px;font-size:13px;flex-wrap:wrap; }
.overview-context > span { color:#58695e;overflow-wrap:anywhere; }
@media (max-width: 1150px) { .overview-columns { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .overview-sheet { padding: 18px; } .overview-facts > div { grid-template-columns: 1fr; gap: 5px; } }
</style>
