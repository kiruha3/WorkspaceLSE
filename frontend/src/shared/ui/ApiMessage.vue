<script setup lang="ts">
import { computed } from 'vue'
import { ApiError } from '../../api/client'
const props = defineProps<{ error: unknown }>()
const message = computed(() => props.error instanceof Error ? props.error.message : 'Не удалось выполнить операцию. Повторите запрос.')
const fields = computed(() => props.error instanceof ApiError ? Object.entries(props.error.fieldErrors).map(([key, value]) => ({ key, value: Array.isArray(value) ? value.join(' · ') : String(value) })) : [])
const documentConflict=computed(()=>props.error instanceof ApiError&&props.error.code==='document_version_conflict')
const conflict = computed(() => props.error instanceof ApiError && props.error.status === 409&&!documentConflict.value)
</script>
<template>
  <div v-if="error" class="message message-error" role="alert">
    <strong>{{ documentConflict?'Конфликт версии документа':conflict ? 'Конфликт изменений' : 'Операция не выполнена' }}</strong>
    <p>{{ message }}</p>
    <p v-if="conflict">Ваши изменения сохранены в форме. Обновите запись, чтобы увидеть серверную версию, и согласуйте изменения.</p>
    <ul v-if="fields.length"><li v-for="field in fields" :key="field.key">{{ field.key }}: {{ field.value }}</li></ul>
  </div>
</template>
