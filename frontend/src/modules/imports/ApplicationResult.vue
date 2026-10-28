<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { ImportApplication } from '../../api/imports'
defineProps<{ application: ImportApplication }>()
</script>
<template>
  <section data-application-result class="card stack-card" role="status">
    <p class="eyebrow">Серверный протокол</p><h2>Пакет применён</h2><p>Создано: {{ application.created_count }} · Ранее перенесено: {{ application.existing_count }}.</p>
    <p class="muted compact">Исторические записи доступны в основном реестре. Это не подтверждение нового окончания, выдачи или квалификации.</p>
    <ul><li v-for="item in application.items" :key="item.row_id"><RouterLink data-applied-work :to="`/expertises/${item.expertise_id}`">Открыть рабочую экспертизу</RouterLink> · {{ item.action === 'created' ? 'создана' : 'сохранена прежняя связь' }}</li></ul>
    <p class="muted compact">Протокол {{ application.id }} · {{ application.created_at }}</p>
  </section>
</template>
