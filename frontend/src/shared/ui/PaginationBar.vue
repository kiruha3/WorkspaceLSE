<script setup lang="ts">
defineProps<{ page: number; count: number; next: boolean; previous: boolean; busy: boolean }>()
defineEmits<{ change: [page: number] }>()
</script>
<template><div class="pagination"><span>Всего: {{ count }} · Страница {{ page }}</span><div class="button-row"><button :disabled="!previous || busy" @click="$emit('change', page - 1)">Назад</button><button :disabled="!next || busy" @click="$emit('change', page + 1)">Далее</button></div></div></template>
