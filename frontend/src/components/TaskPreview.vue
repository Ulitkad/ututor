<script setup>
import { computed } from 'vue'
import { displayOption, taskSegments } from '../utils'
const props = defineProps({ item: Object, category: String, solution: Boolean })
const segments = computed(() => taskSegments(props.item))
</script>
<template>
  <span v-if="item.listName" class="task-explanation">{{ item.listName }} · </span>
  <span class="task-preview" :class="{ 'stress-preview': category === 'stress' }"><template v-for="(segment, i) in segments" :key="i"><span v-if="'explanation' in segment" class="task-explanation">[{{ segment.explanation }}]</span><span v-else-if="'text' in segment">{{ segment.text }}</span><span v-else-if="'letter' in segment" :class="{ 'stress-mark': item.data.stress === segment.letter }">{{ segment.value + (item.data.stress === segment.letter ? '\u0301' : '') }}</span><span v-else-if="solution">{{ segment.part.correct }}</span><span v-else class="gap-preview"><span v-if="segment.part.hint" class="gap-hint">{{ segment.part.hint }} → </span><span v-for="(o, j) in segment.part.options" :key="j" :class="{ 'correct-option': j === 0 }">{{ j ? ' | ' : '' }}{{ displayOption(o) }}<span v-if="j === 0" class="text-xs"> ✓</span></span></span></template><span v-if="item.needs_review" class="badge amber ml-3">Требует проверки</span></span>
</template>
<style scoped>
.task-preview { white-space: pre-wrap; }
</style>
