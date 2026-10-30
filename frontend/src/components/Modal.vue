<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
defineProps({ title: String, subtitle: String, wide: Boolean })
const emit = defineEmits(['close'])
const dialog = ref(null)
const previousFocus = document.activeElement
function keydown(e) {
  if (e.key === 'Escape') emit('close')
  if (e.key !== 'Tab') return
  const focusable = [...dialog.value.querySelectorAll('button:not(:disabled),input,textarea,select,[tabindex="0"]')].filter(e => e.offsetParent !== null)
  const first = focusable[0], last = focusable.at(-1)
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() }
}
onMounted(async () => {
  document.body.style.overflow = 'hidden'
  document.addEventListener('keydown', keydown)
  await nextTick()
  ;(dialog.value.querySelector('[autofocus]') || dialog.value.querySelector('input,textarea,button'))?.focus()
})
onBeforeUnmount(() => { document.body.style.overflow = ''; document.removeEventListener('keydown', keydown); previousFocus?.focus() })
</script>
<template>
  <Teleport to="body"><div class="modal-backdrop" @mousedown.self="emit('close')">
    <section ref="dialog" class="modal" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1">
      <header class="modal-header"><div><h2>{{ title }}</h2><p v-if="subtitle" class="muted mt-1 text-sm">{{ subtitle }}</p></div><button class="icon-btn" aria-label="Закрыть" @click="emit('close')"><Icon name="X" /></button></header>
      <slot />
    </section>
  </div></Teleport>
</template>
