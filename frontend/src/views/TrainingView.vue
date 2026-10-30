<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useTraining } from '../stores/training'
import { categoryById, displayOption, percentage, taskSegments, vowels } from '../utils'
import Modal from '../components/Modal.vue'
import TaskPreview from '../components/TaskPreview.vue'
const training = useTraining(), router = useRouter(), route = useRoute()
const index = ref(0), choices = ref([]), feedback = ref(null), busy = ref(false), error = ref(''), results = ref(null), exiting = ref(false), allowLeave = ref(false)
const session = computed(() => training.session)
const current = computed(() => session.value?.items[index.value])
const segments = computed(() => current.value ? taskSegments(current.value) : [])
const category = computed(() => categoryById(session.value?.category))
const gaps = computed(() => current.value?.parts?.filter(p => 'options' in p) || [])
const complete = computed(() => feedback.value?.complete || false)
const pendingChoice = ref(null)
const answered = ref(0)
const loading = ref(true)
const score = computed(() => percentage(results.value?.correct || 0, results.value?.total || 0))
function restore() {
  index.value = session.value.index || 0; choices.value = session.value.choices || []; feedback.value = session.value.feedback || null; answered.value = session.value.answered || 0
}
onMounted(async () => {
  window.addEventListener('keydown', keydown); window.addEventListener('beforeunload', beforeUnload)
  try {
    const id = route.query.session || session.value?.id
    if (!id) { router.replace('/profiles'); return }
    await training.resume(id); restore()
    if (session.value.status === 'finished') results.value = await api(`/sessions/${id}/results`)
  } catch (e) { training.session = null; error.value = e.message } finally { loading.value = false }
})
onBeforeUnmount(() => { window.removeEventListener('keydown', keydown); window.removeEventListener('beforeunload', beforeUnload) })
onBeforeRouteLeave(() => {
  if (allowLeave.value || results.value || !session.value) return true
  if (busy.value) return false
  return window.confirm('Выйти с сохранением тренировки? Вы сможете продолжить с этого места. Новая тренировка по этим же спискам будет недоступна до завершения текущей. По другим спискам тренироваться можно.')
})
function beforeUnload(e) { if (session.value && !results.value) { e.preventDefault(); e.returnValue = '' } }
function keydown(e) {
  if (loading.value || e.repeat || exiting.value || !complete.value || busy.value || results.value || !['Enter', ' '].includes(e.key) || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(document.activeElement?.tagName)) return
  e.preventDefault(); next()
}
async function choose(value) {
  if (busy.value || complete.value) return
  busy.value = true; error.value = ''; pendingChoice.value = value
  const nextChoices = [...choices.value, value]
  try {
    const response = await api(`/sessions/${session.value.id}/answers`, { method: 'POST', body: { item_id: current.value.id, choices: nextChoices } })
    choices.value = nextChoices; feedback.value = response
    if (response.complete) answered.value++
    document.activeElement?.blur()
  } catch (e) { error.value = e.message } finally { busy.value = false; pendingChoice.value = null }
}
async function next() {
  if (!complete.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    if (index.value + 1 === session.value.items.length) results.value = await api(`/sessions/${session.value.id}/finish`, { method: 'POST' })
    else { training.session = await api(`/sessions/${session.value.id}/advance`, { method: 'POST', body: { item_id: current.value.id } }); restore() }
  } catch (e) { error.value = e.message } finally { busy.value = false }
  document.activeElement?.blur()
}
function gapState(i) { return i < choices.value.length ? feedback.value?.results[i] ? 'right' : 'wrong' : i === choices.value.length ? 'active' : 'waiting' }
function stressState(i) {
  if (!feedback.value) return ''
  if (i === feedback.value.correct_answers[0]) return 'right'
  if (i === choices.value[0]) return 'wrong'
  return 'dim'
}
async function retryMistakes() {
  busy.value = true; error.value = ''
  try {
    await training.start(results.value.profile_id, results.value.list_ids, results.value.mistakes.map(i => i.id))
    await router.replace({ path: '/training', query: { session: session.value.id } })
    index.value = 0; choices.value = []; feedback.value = null; answered.value = 0; results.value = null
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
function returnToProfile() { allowLeave.value = true; router.push({ path: `/profiles/${session.value.profile_id}`, query: { category: session.value.category } }) }
function pause() { exiting.value = false; returnToProfile() }
async function finish() {
  busy.value = true; error.value = ''
  try { results.value = await api(`/sessions/${session.value.id}/finish`, { method: 'POST' }); exiting.value = false }
  catch (e) { error.value = e.message } finally { busy.value = false }
}
</script>
<template>
  <div v-if="loading" class="loading"><Icon name="LoaderCircle" class="spin" />Открываем тренировку…</div>
  <div v-else-if="session" class="training-page">
    <header class="training-header"><a class="brand" href="#" @click.prevent="results ? returnToProfile() : (exiting = true)"><div class="brand-symbol">u<span></span></div><span>uTutor<span class="brand-dot">.</span></span></a><span class="training-context"><Icon :name="category.icon" :size="17" />{{ category.name }}<span class="training-divider">/</span><span>{{ session.name }}</span></span><button class="btn secondary sm" :disabled="busy" @click="results ? returnToProfile() : (exiting = true)"><Icon name="X" :size="15" />{{ results ? 'В профиль' : 'Завершить тренировку' }}</button></header>
    <template v-if="!results && current"><div class="training-session-progress"><div><span>Задание</span><strong>{{ index + 1 }} <span>из {{ session.items.length }}</span></strong></div><div class="progress-track"><div :style="{ width: percentage(answered, session.items.length) + '%' }"></div></div></div>
      <main class="training-main"><div class="training-question-label"><Icon :name="category.icon" :size="16" />{{ session.category === 'stress' ? 'НАЖМИТЕ НА УДАРНУЮ ГЛАСНУЮ' : session.category === 'spelling' ? 'ВЫБЕРИТЕ ПРАВИЛЬНОЕ НАПИСАНИЕ' : 'ВЫБЕРИТЕ ВЕРНУЮ ФОРМУ СЛОВА' }}</div>
        <div v-if="session.category === 'stress'" class="training-word stress-word"><template v-for="(segment, i) in segments" :key="`${index}-${i}`"><span v-if="'explanation' in segment" class="training-explanation">[{{ segment.explanation }}]</span><span v-else-if="'text' in segment">{{ segment.text }}</span><button v-else-if="vowels.includes(segment.value)" :class="stressState(segment.letter)" :disabled="busy || complete" :aria-label="`Ударение на ${segment.value}, буква ${segment.letter + 1}`" @click="choose(segment.letter)">{{ segment.value + (feedback?.correct_answers[0] === segment.letter ? '\u0301' : '') }}</button><span v-else :class="{ dim: complete }">{{ segment.value }}</span></template></div>
        <div v-else class="training-word" :class="{ 'grammar-sentence': session.category === 'grammar' }"><template v-for="(segment, p) in segments" :key="`${index}-${p}`"><span v-if="'explanation' in segment" class="training-explanation">[{{ segment.explanation }}]</span><span v-else-if="'text' in segment">{{ segment.text }}</span><span v-else class="answer-gap" :class="[gapState(segment.gap), { 'resolved-empty': segment.gap < choices.length && feedback?.results[segment.gap] && choices[segment.gap] === '' }]"><template v-if="segment.gap < choices.length"><span class="chosen-answer" :class="{ 'empty-answer': choices[segment.gap] === '' }">{{ feedback.results[segment.gap] ? choices[segment.gap] : displayOption(choices[segment.gap]) }}</span><span v-if="!feedback.results[segment.gap]" class="correct-answer" :class="{ 'empty-answer': feedback.correct_answers[segment.gap] === '' }">{{ displayOption(feedback.correct_answers[segment.gap]) }}</span></template><span v-else-if="session.category === 'grammar'" class="grammar-hint">({{ segment.part.hint }})</span><span v-else class="gap-underscore">_</span></span></template></div>
        <div v-if="session.category !== 'stress' && !complete" class="training-options"><button v-for="(option, o) in gaps[choices.length]?.options" :key="`${index}-${choices.length}-${o}`" class="answer-option" :disabled="busy" @click="choose(option)"><span>{{ displayOption(option) }}</span><small v-if="option === ''">без символа</small><small v-else-if="option === ' '">пробел</small><Icon v-if="busy && pendingChoice === option" name="LoaderCircle" class="spin" :size="15" /></button></div>
        <div v-if="session.category !== 'stress' && gaps.length > 1" class="gap-steps"><span v-for="(_, g) in gaps" :key="g" :class="{ done: g < choices.length, active: g === choices.length }"></span><small>Пропуск {{ Math.min(choices.length + 1, gaps.length) }} из {{ gaps.length }}</small></div>
        <div class="training-feedback-space"><div v-if="complete" class="answer-feedback" :class="feedback.correct ? 'success' : 'mistake'"><Icon :name="feedback.correct ? 'CircleCheck' : 'CircleHelp'" :size="20" /><div><strong>{{ feedback.correct ? 'Верно' : 'Неверно' }}</strong><p v-if="!feedback.correct">Это задание можно будет отработать в конце тренировки.</p></div></div><p v-else-if="session.category === 'stress'" class="training-tip">Гласные подсвечены — выберите ударную</p></div>
        <div v-if="error" class="error-box training-error">{{ error }}</div><button v-if="complete" class="btn primary next-button" :disabled="busy" @click="next">{{ index + 1 === session.items.length ? 'Посмотреть результаты' : 'Дальше' }}<Icon :name="busy ? 'LoaderCircle' : 'ArrowRight'" :class="{ spin: busy }" :size="17" /></button><span v-if="complete" class="keyboard-tip"><Icon name="Keyboard" :size="15" />или нажмите Enter / Пробел</span>
      </main><footer class="training-footer"><Icon name="ShieldCheck" :size="14" />Прогресс сохраняется после каждого задания</footer>
    </template>
    <main v-else-if="results" class="results-main"><h1>Результаты тренировки</h1><p v-if="!results.total" class="muted mt-4">Вы не завершили ни одного задания. Статистика не изменилась.</p>
      <div class="results-card card">
        <div class="score-ring" :style="{ background: `conic-gradient(#61b99f ${score * 3.6}deg, #eef4f8 0deg)` }"><div><strong>{{ score }}<span>%</span></strong><small>верных ответов</small></div></div>
        <div class="result-stats"><div><span>Всего пройдено</span><strong>{{ results.total }}</strong></div><div class="correct"><span><Icon name="CircleCheck" :size="17" />Верно</span><strong>{{ results.correct }}</strong></div><div class="mistake"><span><Icon name="CircleX" :size="17" />С ошибками</span><strong>{{ results.mistakes.length }}</strong></div></div>
         <div v-if="results.mistakes.length" class="result-mistakes"><h3>Задания с ошибками<span>{{ results.mistakes.length }}</span></h3><p>Правильные ответы</p><div class="mistake-list"><div v-for="item in results.mistakes" :key="item.id"><span class="mistake-dot"></span><span><TaskPreview :item="item" :category="session.category" solution /></span><Icon name="Check" :size="17" /></div></div></div>
        <div v-else-if="results.total" class="perfect-result"><Icon name="CheckCheck" :size="20" />Все пройденные задания выполнены верно</div>
        <div class="result-actions"><button v-if="results.mistakes.length" class="btn primary" :disabled="busy" @click="retryMistakes"><Icon :name="busy ? 'LoaderCircle' : 'RotateCcw'" :class="{ spin: busy }" :size="16" />Отработать ошибки</button><button class="btn secondary" :disabled="busy" @click="returnToProfile">Вернуться в профиль<Icon name="ArrowRight" :size="16" /></button></div>
        <div v-if="error" class="error-box mt-4">{{ error }}</div>
      </div><p class="result-saved"><Icon name="ShieldCheck" :size="13" />Результаты уже сохранены в учебном профиле</p></main>
  </div>
  <div v-else-if="error" class="error-box">{{ error }} <RouterLink to="/profiles">Вернуться к профилям</RouterLink></div>
   <Modal v-if="exiting" title="Завершить тренировку?" @close="!busy && (exiting = false)"><div class="modal-body"><p>Сохраните тренировку, чтобы позже продолжить с этого же места, включая ответы в текущем слове. Пока она не завершена, нельзя начать новую только по участвующим в ней спискам. По остальным спискам тренироваться можно.</p><p class="mt-4 muted">Если завершить полностью, вы увидите итог только по завершённым заданиям. Нерешённые задания не повлияют на статистику.</p><div v-if="error" class="error-box mt-4">{{ error }}</div></div><footer class="modal-footer flex-wrap"><button class="btn secondary" :disabled="busy" @click="exiting = false">Назад</button><button class="btn secondary" :disabled="busy" @click="finish">Завершить полностью</button><button class="btn primary" :disabled="busy" @click="pause">Сохранить и выйти</button></footer></Modal>
</template>
<style scoped>
.training-word .training-explanation{font-size:.65em;color:#64748b;letter-spacing:normal;overflow-wrap:anywhere}
.training-word{white-space:pre-wrap}
.answer-gap.resolved-empty{display:inline;padding:0;margin:0;border:0;min-width:0;background:none}
.answer-gap.resolved-empty .chosen-answer{display:none}
.results-main .results-card { margin-top: 28px; }
.training-page{min-height:100dvh;background:radial-gradient(ellipse at 50% 5%,#eaf5ff80,transparent 50%),#fff;display:flex;flex-direction:column}.training-header{height:92px;border-bottom:1px solid #ebf0f6;display:flex;align-items:center;justify-content:space-between;gap:20px;padding:0 5vw}.training-header .brand{font-size:25px;padding:0}.training-header .brand-symbol{width:32px;height:32px;font-size:27px;line-height:28px;border-radius:10px}.training-context{display:flex;gap:10px;align-items:center;font-size:11px;color:#8498ad;max-width:60%;min-width:0}.training-context>span:last-child{overflow:hidden;white-space:nowrap;text-overflow:ellipsis}.training-divider{color:#ccd7e2;margin:0 5px}.training-session-progress{max-width:780px;width:calc(100% - 50px);margin:34px auto 0}.training-session-progress>div:first-child{display:flex;justify-content:space-between;font-size:10px;color:#9babbc;margin-bottom:11px}.training-session-progress strong{font-size:12px;color:#6d95b5;font-weight:500}.training-session-progress strong>span{font-size:10px;color:#afbbc9;margin-left:3px}.training-session-progress .progress-track{height:4px;background:#ecf3fa}.training-session-progress .progress-track>div{background:#88c6ee}.training-main{display:flex;align-items:center;flex-direction:column;flex:1;max-width:1080px;width:calc(100% - 50px);margin:0 auto;padding:65px 0 35px;text-align:center}.training-question-label{display:flex;gap:8px;align-items:center;font-size:9px;letter-spacing:1.5px;color:#89a4bc;margin-bottom:45px}.training-word{font-size:55px;font-weight:500;letter-spacing:1px;line-height:1.8;padding:0 10px;color:#344c66;overflow-wrap:anywhere;max-width:100%}.stress-word{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:2px;line-height:1.5}.stress-word button{border:1px solid #e4eff9;background:#f0f8ff;color:#4298c9;padding:0 5px;min-width:43px;position:relative;border-radius:11px;margin:0 3px;font-size:inherit;font-weight:inherit;opacity:1}.stress-word button:hover:not(:disabled){background:#dff1ff;border-color:#a4d5f3;transform:translateY(-3px)}.stress-word button.right{color:#389b79;background:#eaf9f1;border-color:#b9e8d4}.stress-word button.wrong{color:#d96d80;background:#fff0f2;border-color:#f2cbd3}.stress-word .dim{color:#aebbc9}.training-accent{position:absolute;left:45%;top:-5px}.answer-gap{display:inline;position:relative;margin:0 2px;border-radius:7px;box-decoration-break:clone;-webkit-box-decoration-break:clone}.answer-gap.active{color:#0284c7}.answer-gap.active .gap-underscore{border-bottom:3px solid #7fc5ed;animation:pulse 1.6s infinite;display:inline-block;min-width:37px;color:transparent;height:1.32em;vertical-align:baseline}.answer-gap.waiting{color:#c6d7e6}.answer-gap.waiting .gap-underscore{border-bottom:2px solid #d9e5ef;display:inline-block;min-width:32px;color:transparent;height:1.32em}.answer-gap.right{color:#389e7b}.answer-gap.wrong .chosen-answer{text-decoration:line-through;color:#df8393;font-size:.74em}.correct-answer{color:#389e7b;font-size:.64em;vertical-align:super;margin-left:4px;letter-spacing:0}.empty-answer{display:inline-block;background:#eaf9f2;border:1px solid #bce9d6;line-height:1.35;border-radius:7px;font-size:.65em;padding:1px 7px;vertical-align:middle;min-width:27px;margin:0 2px}.wrong .chosen-answer.empty-answer{background:#fff0f2;border-color:#f3cdd5;color:#d7798c;font-size:.65em}.correct-answer.empty-answer{font-size:.5em;vertical-align:super}.grammar-sentence{font-size:29px;line-height:1.85;letter-spacing:-.5px;max-width:850px}.grammar-hint{color:#80b0cf;background:#eff7ff;border-bottom:1px dashed #b5d7ef;padding:1px 6px;border-radius:5px}.training-options{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:35px}.answer-option{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-width:82px;min-height:65px;padding:12px 23px;border:1px solid #dfe8f1;background:#fff;border-radius:13px;color:#617e99;font-size:23px;box-shadow:0 3px 8px #0f172a03}.answer-option small{font-size:8px;font-weight:400;color:#a8b6c5}.answer-option:hover:not(:disabled){border-color:#7ac3ee;color:#0284c7;background:#f5fbff;transform:translateY(-3px)}.gap-steps{display:flex;align-items:center;gap:5px;margin-top:25px}.gap-steps>span{width:5px;height:5px;background:#dce7f1;border-radius:50%}.gap-steps>span.done{background:#75c2a6}.gap-steps>span.active{background:#79bce6}.gap-steps small{font-size:8px;color:#a0b2c4;margin-left:6px}.training-feedback-space{min-height:120px;display:flex;align-items:center;justify-content:center;width:100%;padding-top:20px}.answer-feedback{display:flex;gap:12px;align-items:center;padding:17px 23px;background:#f0faf6;border:1px solid #dbf0e5;border-radius:12px;color:#57a489;text-align:left;max-width:100%}.answer-feedback>svg{flex-shrink:0}.answer-feedback strong{font-size:12px;font-weight:500}.answer-feedback p{font-size:9px;color:#8bb5a4;margin-top:5px;line-height:1.7}.answer-feedback.mistake{background:#fffbf6;border-color:#f7ead9;color:#b59b72}.answer-feedback.mistake p{color:#c0b29d}.training-tip{font-size:10px;color:#acb9c8}.next-button{padding:12px 26px;min-height:44px;min-width:160px;margin-top:5px}.keyboard-tip{display:flex;gap:6px;align-items:center;font-size:9px;color:#afbdcc;margin-top:15px}.training-footer{display:flex;gap:7px;align-items:center;justify-content:center;color:#adbbc9;font-size:9px;padding:25px}.training-error{margin-bottom:15px;max-width:500px}.results-main{max-width:700px;margin:55px auto;padding:0 25px;text-align:center;width:100%}.result-celebration{display:flex;justify-content:center;align-items:center;gap:8px;color:#86b3d3;font-size:9px;letter-spacing:1.5px;margin-bottom:18px}.results-main h1{font-size:31px;letter-spacing:-.8px}.results-subtitle{font-size:11px;color:#95a9bd;margin:13px 0 28px;line-height:1.9}.results-card{padding:33px;border-radius:24px}.score-ring{width:165px;height:165px;border-radius:50%;margin:0 auto 29px;padding:7px;box-shadow:0 0 0 8px #f7fbf9}.score-ring>div{width:100%;height:100%;background:white;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center}.score-ring strong{font-size:42px;color:#478f77;font-weight:550;letter-spacing:-2px}.score-ring strong>span{font-size:23px;margin-left:3px;letter-spacing:-1px}.score-ring small{font-size:9px;color:#a0b8ac;margin-top:2px}.result-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid #edf2f7;border-bottom:1px solid #edf2f7;padding:21px 0}.result-stats>div{border-right:1px solid #edf2f7;display:flex;flex-direction:column;align-items:center;gap:10px}.result-stats>div:last-child{border:0}.result-stats>div>span{display:flex;align-items:center;gap:5px;font-size:9px;color:#9bafc0}.result-stats strong{font-size:25px;font-weight:500;color:#7692a7}.result-stats .correct strong{color:#5ba98d}.result-stats .mistake strong{color:#d08293}.result-mistakes{text-align:left;margin:25px 0}.result-mistakes h3{display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#7391a7}.result-mistakes h3>span{font-size:9px;color:#bd8f9b;background:#fff2f4;padding:2px 6px;border-radius:4px}.result-mistakes>p{font-size:9px;color:#a6b7c7;margin-top:7px}.mistake-list{max-height:220px;overflow:auto;margin-top:14px}.mistake-list>div{display:flex;align-items:center;gap:10px;padding:11px 0;border-bottom:1px solid #f1f4f8;font-size:13px;color:#649583;line-height:1.8}.mistake-dot{width:4px;height:4px;border-radius:50%;background:#db9ba8;flex-shrink:0}.mistake-list>div>svg{color:#a0c9b9;flex-shrink:0;margin-left:auto}.perfect-result{display:flex;align-items:center;justify-content:center;gap:9px;color:#7aaa97;font-size:11px;margin:30px 0;line-height:1.8}.result-actions{display:flex;justify-content:center;gap:10px;margin-top:25px}.result-actions .btn{font-size:11px;flex:1}.result-saved{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:23px;font-size:9px;color:#a3b5c5}@keyframes pulse{50%{border-color:#0284c7}}@media(max-width:760px){.training-header{height:75px;padding:0 20px;gap:10px}.training-context{display:none}.training-session-progress{margin-top:25px}.training-main{padding-top:50px;width:calc(100% - 35px)}.training-question-label{font-size:8px;letter-spacing:.8px;margin-bottom:30px}.training-word{font-size:39px;padding:0}.stress-word{gap:0}.stress-word button{min-width:28px;padding:0 3px;margin:0 1px;border-radius:8px}.grammar-sentence{font-size:23px;line-height:1.9}.answer-option{font-size:20px;min-width:60px;min-height:57px;padding:10px 18px;border-radius:10px}.training-options{gap:8px;margin-top:25px}.answer-feedback{padding:13px 15px;gap:8px}.answer-feedback strong{font-size:11px}.answer-feedback p{font-size:8px}.results-main{margin-top:40px;padding:0 20px}.results-main h1{font-size:27px}.results-subtitle{font-size:10px}.results-card{padding:25px 20px}.result-stats>div>span{font-size:8px;gap:3px}.result-actions{flex-direction:column}.score-ring{width:145px;height:145px}.result-stats strong{font-size:23px}.perfect-result{font-size:10px}}
</style>
