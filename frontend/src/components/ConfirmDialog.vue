<script setup>
import { ref } from 'vue'
import Modal from './Modal.vue'
defineProps({ title: String, message: String, action: { type: String, default: 'Удалить' } })
const emit = defineEmits(['close', 'confirm'])
const busy = ref(false)
function confirm() { busy.value = true; emit('confirm', () => { busy.value = false }) }
</script>
<template><Modal :title="title" @close="!busy && emit('close')"><div class="modal-body"><div class="warning-symbol"><Icon name="AlertCircle" :size="26" /></div><p class="muted leading-relaxed">{{ message }}</p></div><footer class="modal-footer"><button class="btn secondary" :disabled="busy" @click="emit('close')">Отмена</button><button class="btn danger" :disabled="busy" @click="confirm"><Icon v-if="busy" name="LoaderCircle" class="spin" :size="17" />{{ action }}</button></footer></Modal></template>
