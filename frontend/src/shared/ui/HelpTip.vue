<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

defineProps<{ label: string }>()
const id = `help-${useId()}`, trigger = ref<HTMLButtonElement | null>(null), popup = ref<HTMLElement | null>(null)
const shown = ref(false), pinned = ref(false), position = ref({ left: '12px', top: '12px' })
let hovered = false, focused = false, timer: ReturnType<typeof setTimeout> | undefined
function cancelClose() { clearTimeout(timer); timer = undefined }
function show() { cancelClose(); shown.value = true }
function hide() { cancelClose(); shown.value = false; pinned.value = false }
function enter() { hovered = true; show() }
function leave() {
 hovered = false; cancelClose()
 timer = setTimeout(() => { if (!hovered && !focused && !pinned.value) hide() }, 120)
}
function focus() { focused = true; show() }
function blur() { focused = false; leave() }
function toggle() { if (pinned.value) hide(); else { pinned.value = true; show() } }
function place() {
 if (!trigger.value || !popup.value) return
 const anchor = trigger.value.getBoundingClientRect(), box = popup.value.getBoundingClientRect()
 const width = window.innerWidth, height = window.innerHeight
 const left = Math.max(12, Math.min(anchor.left, width - box.width - 12))
 const below = anchor.bottom + 8
 const top = below + box.height <= height - 12 ? below : Math.max(12, Math.min(anchor.top - box.height - 8, height - box.height - 12))
 position.value = { left: `${left}px`, top: `${top}px` }
}
function outside(event: Event) {
 const target = event.target as Node | null
 if (target && !trigger.value?.contains(target) && !popup.value?.contains(target)) hide()
}
function escape(event: KeyboardEvent) { if (event.key === 'Escape') { event.preventDefault(); hide() } }
watch(shown, (value, _, cleanup) => {
 if (!value) return
 void nextTick(place)
 window.addEventListener('resize', place)
 window.addEventListener('scroll', place, true)
 document.addEventListener('pointerdown', outside)
 document.addEventListener('click', outside)
 document.addEventListener('focusin', outside)
 document.addEventListener('keydown', escape)
 cleanup(() => {
  window.removeEventListener('resize', place)
  window.removeEventListener('scroll', place, true)
  document.removeEventListener('pointerdown', outside)
  document.removeEventListener('click', outside)
  document.removeEventListener('focusin', outside)
  document.removeEventListener('keydown', escape)
 })
})
onBeforeUnmount(cancelClose)
</script>

<template>
 <span class="help-tip"><button ref="trigger" type="button" class="help-trigger" :aria-label="`Пояснение: ${label}`" :aria-describedby="shown ? id : undefined" @mouseenter="enter" @mouseleave="leave" @focus="focus" @blur="blur" @click.stop.prevent="toggle" @keydown.esc.stop.prevent="hide">?</button><Teleport to="body"><span v-if="shown" :id="id" ref="popup" role="tooltip" class="help-popup" :style="position" @mouseenter="enter" @mouseleave="leave"><slot /></span></Teleport></span>
</template>

<style scoped>
.help-tip{display:inline-flex;vertical-align:middle;align-items:center;justify-self:start;margin-inline-start:5px;font-size:12px;line-height:1}
.help-trigger{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;min-height:22px;padding:0;border:1px solid #b8c9b9;border-radius:50%;background:#f7faf5;color:var(--green);font-size:12px;font-weight:700;line-height:1;cursor:help}
.help-popup{position:fixed;z-index:1000;width:max-content;max-width:min(340px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:auto;padding:12px 14px;border:1px solid #c7d5c5;border-radius:8px;background:#fff;color:var(--ink);box-shadow:0 5px 20px #15382026;font-family:'Segoe UI',Arial,sans-serif;font-size:12px;font-weight:400;line-height:1.6;letter-spacing:normal;text-transform:none;white-space:normal;overflow-wrap:anywhere}
.help-popup :deep(p){margin:0}.help-popup :deep(code){font-size:11px}
</style>
