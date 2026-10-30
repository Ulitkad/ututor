import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUI = defineStore('ui', () => {
  const toasts = ref([])
  function notify(message, type = 'success') {
    const id = crypto.randomUUID()
    toasts.value.push({ id, message, type })
    setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id) }, 5000)
  }
  return { toasts, notify }
})
