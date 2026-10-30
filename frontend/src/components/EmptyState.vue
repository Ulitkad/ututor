<script setup>
defineProps({ icon: { type: String, default: 'Folder' }, title: String, text: String, action: String })
defineEmits(['action'])
</script>
<template><div class="empty-state"><div class="empty-icon"><Icon :name="icon" :size="32" /></div><h3>{{ title }}</h3><p>{{ text }}</p><button v-if="action" class="btn primary mt-5" @click="$emit('action')"><Icon name="Plus" :size="17" />{{ action }}</button></div></template>
