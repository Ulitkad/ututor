<script setup>
import { displayOption } from '../utils'
defineProps({ item: Object, category: String })
</script>
<template>
  <span v-if="category === 'stress'" class="stress-preview"><template v-for="(letter, i) in item.data.word" :key="i"><span :class="{ 'stress-mark': item.data.stress === i }">{{ letter }}<span v-if="item.data.stress === i" class="accent-mark">́</span></span></template><span v-if="item.needs_review" class="badge amber ml-3">Требует проверки</span></span>
  <span v-else class="task-preview"><template v-for="(part, i) in item.data.parts" :key="i"><span v-if="'text' in part">{{ part.text }}</span><span v-else class="gap-preview"><span v-if="part.hint" class="gap-hint">{{ part.hint }} → </span><span v-for="(o, j) in part.options" :key="j" :class="{ 'correct-option': j === 0 }">{{ j ? ' | ' : '' }}{{ displayOption(o) }}<span v-if="j === 0" class="text-xs"> ✓</span></span></span></template></span>
</template>
