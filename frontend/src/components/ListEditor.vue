<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { categoryById, displayOption, duplicateRowIndexes, importPrompt, normalizeOption, serializeTask, vowels } from '../utils'
import Modal from './Modal.vue'
import TaskPreview from './TaskPreview.vue'

const props = defineProps({ config: Object })
const emit = defineEmits(['close', 'saved'])
const category = computed(() => categoryById(props.config.category))
const name = ref(''), mode = ref(props.config.mode || 'visual'), raw = ref(''), rows = ref([])
const loading = ref(false), busy = ref(false), error = ref(''), dragging = ref(false), active = ref(0)
const word = ref(''), text = ref(''), parts = ref([]), stress = ref(null), selection = ref({ start: 0, end: 0 }), textInput = ref(null)
const optionModal = ref(null), distractors = ref(''), hint = ref(''), correct = ref('')
const selectionPopover = ref(false)
const explanation = ref(''), copied = ref(false), rawNumbers = ref(null)
const lineNumbers = computed(() => raw.value.split('\n').length)
async function copyPrompt() {
  error.value = ''; copied.value = false
  const value = importPrompt(props.config.category)
  try { await navigator.clipboard.writeText(value); copied.value = true }
  catch {
    const input = document.createElement('textarea'), previous = document.activeElement
    input.value = value; input.style.cssText = 'position:fixed;opacity:0'; document.body.append(input); input.select()
    try { copied.value = document.execCommand('copy') } catch { copied.value = false }
    finally { input.remove(); previous?.focus() }
    if (!copied.value) error.value = 'Не удалось скопировать промт. Разрешите доступ к буферу обмена и откройте сайт по HTTPS или localhost.'
  }
}
const reviewCount = computed(() => rows.value.filter(r => r.needs_review).length)
const duplicateIndexes = computed(() => duplicateRowIndexes(rows.value))
const dirty = ref(false)
const lines = computed(() => raw.value.split('\n').filter(s => s.trim()).length)
onMounted(async () => {
  if (!props.config.id) return
  loading.value = true
  try {
    const data = await api(`/lists/${props.config.id}`)
    name.value = data.name; raw.value = data.raw; rows.value = data.items
  } catch (e) { error.value = e.message } finally { loading.value = false }
})
function close() {
  if (optionModal.value) { optionModal.value = null; return }
  if (!busy.value && (!dirty.value || window.confirm('Закрыть редактор без сохранения изменений?'))) emit('close')
}
function serialize(data) {
  return serializeTask({ ...data, explanation: explanation.value.trim() }, props.config.category)
}
async function switchMode(next) {
  error.value = ''
  if (next === mode.value) return
  if (mode.value === 'raw' && raw.value.trim()) {
    busy.value = true
    try { rows.value = await api('/parse', { method: 'POST', body: { category: props.config.category, raw: raw.value } }) }
    catch (e) { error.value = e.message; return } finally { busy.value = false }
  } else if (mode.value === 'raw') rows.value = []
  if (next === 'raw') raw.value = rows.value.map(r => r.source).join('\n')
  mode.value = next
}
async function upload(file) {
  if (!file) return
  error.value = ''; busy.value = true
  try {
    const form = new FormData(); form.append('file', file)
    const data = await api(`/import?category=${props.config.category}`, { method: 'POST', body: form })
    if (rows.value.length && !window.confirm('Заменить текущие задания содержимым файла?')) return
    raw.value = data.raw; rows.value = data.items; dirty.value = true
    if (!name.value) name.value = file.name.replace(/\.txt$/i, '')
    mode.value = 'visual'
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
function dropped(e) { dragging.value = false; upload(e.dataTransfer.files[0]) }
function clearBuilder() { explanation.value = ''; word.value = ''; stress.value = null; text.value = ''; parts.value = []; active.value = 0; selection.value = { start: 0, end: 0 } }
function editRow(row, index) {
  active.value = index + 1
  explanation.value = row.data.explanation || ''
  if (props.config.category === 'stress') { word.value = row.data.word; stress.value = row.data.stress }
  else {
    parts.value = JSON.parse(JSON.stringify(row.data.parts))
    text.value = parts.value.map(p => 'text' in p ? p.text : '▢').join('')
  }
}
function wordChanged() { word.value = word.value.toLowerCase(); stress.value = null; dirty.value = true }
function captureSelection(e) {
  selection.value = { start: e.target.selectionStart, end: e.target.selectionEnd }
  selectionPopover.value = props.config.category === 'spelling' && e.target.selectionEnd > e.target.selectionStart
}
function textChanged() {
  dirty.value = true
  // Preserve gap definitions in order while the teacher edits surrounding text.
  const gaps = parts.value.filter(p => 'options' in p)
  let index = 0
  parts.value = text.value.split('▢').flatMap((s, i, all) => [ ...(s ? [{ text: s }] : []), ...(i < all.length - 1 && gaps[index] ? [gaps[index++]] : []) ])
}
function openGap(empty = false) {
  selectionPopover.value = false
  const { start, end } = selection.value
  if (!empty && props.config.category === 'spelling' && start === end) { error.value = 'Выделите букву или буквосочетание в поле текста.'; return }
  if (text.value.slice(start, end).includes('▢')) { error.value = 'Чтобы изменить существующий пропуск, используйте его карточку ниже.'; return }
  correct.value = empty ? '' : text.value.slice(start, end)
  hint.value = ''; distractors.value = ''; optionModal.value = { start, end, empty }
}
function addGap() {
  const { start, end } = optionModal.value
  const gapIndex = [...text.value.slice(0, start)].filter(c => c === '▢').length
  const gaps = parts.value.filter(p => 'options' in p)
  const normalize = props.config.category === 'spelling' ? normalizeOption : value => value.trim()
  const options = [normalize(correct.value), ...distractors.value.split(',').map(normalize)]
  if (new Set(options).size !== options.length) { error.value = 'Варианты не должны повторяться.'; return }
  gaps.splice(gapIndex, 0, { hint: hint.value.trim(), options, correct: options[0] })
  text.value = text.value.slice(0, start) + '▢' + text.value.slice(end)
  let index = 0
  parts.value = text.value.split('▢').flatMap((s, i, all) => [ ...(s ? [{ text: s }] : []), ...(i < all.length - 1 ? [gaps[index++]] : []) ])
  optionModal.value = null; error.value = ''
}
function updateOptions(part, event) { part.options = [part.options[0], ...event.target.value.split(',').map(props.config.category === 'spelling' ? normalizeOption : o => o.trim())]; part.correct = part.options[0] }
async function addRow() {
  error.value = ''; busy.value = true
  try {
    const data = props.config.category === 'stress' ? { word: word.value, stress: stress.value } : { parts: parts.value.map(p => 'options' in p ? { ...p, correct: p.options[0] } : p) }
    const source = serialize(data)
    const parsed = await api('/parse', { method: 'POST', body: { category: props.config.category, raw: source } })
    if (active.value) rows.value.splice(active.value - 1, 1, parsed[0]); else rows.value.push(parsed[0])
    raw.value = rows.value.map(r => r.source).join('\n'); dirty.value = true; clearBuilder()
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
function removeRow(index) { rows.value.splice(index, 1); raw.value = rows.value.map(r => r.source).join('\n'); dirty.value = true; clearBuilder() }
async function save() {
  error.value = ''; busy.value = true
  try {
    if (mode.value === 'visual' && (word.value.trim() || text.value.trim() || explanation.value.trim())) throw new Error('Сначала добавьте или сохраните задание в конструкторе ниже.')
    const payload = { name: name.value, raw: mode.value === 'raw' ? raw.value : rows.value.map(r => r.source).join('\n') }
    await api(props.config.id ? `/lists/${props.config.id}` : `/folders/${props.config.folderId}/lists`, { method: props.config.id ? 'PUT' : 'POST', body: payload })
    emit('saved')
  } catch (e) { error.value = e.message } finally { busy.value = false }
}
function exportRaw() {
  const blob = new Blob([mode.value === 'raw' ? raw.value : rows.value.map(r => r.source).join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob), a = document.createElement('a')
  a.href = url; a.download = `${name.value || 'Задания'}.txt`; a.click(); URL.revokeObjectURL(url)
}
</script>
<template>
  <Modal :title="config.id ? 'Редактор списка' : 'Новый список заданий'" :subtitle="category.name" wide @close="close">
    <div v-if="loading" class="loading"><Icon name="LoaderCircle" class="spin" />Загружаем список…</div>
    <div v-else class="modal-body editor-body">
      <div class="field"><label for="list-name">Название списка</label><input id="list-name" v-model="name" class="input" placeholder="Например, Сложные ударения · ЕГЭ" required maxlength="120" autofocus @input="dirty = true" /></div>
      <div class="editor-toolbar"><div class="tabs"><button :class="{ active: mode === 'visual' }" :disabled="busy" @click="switchMode('visual')"><Icon name="SlidersHorizontal" :size="13" />Визуальный</button><button :class="{ active: mode === 'raw' }" :disabled="busy" @click="switchMode('raw')"><Icon name="FileText" :size="13" />Текстовый (Raw)</button><button :class="{ active: mode === 'import' }" :disabled="busy" @click="switchMode('import')"><Icon name="Upload" :size="13" />Импорт</button></div><button class="icon-btn" title="Скачать .txt" aria-label="Скачать список" @click="exportRaw"><Icon name="Download" :size="16" /></button></div>
      <div v-if="mode !== 'visual'" class="prompt-toolbar"><button class="btn secondary sm" @click="copyPrompt"><Icon name="Copy" :size="16" />{{ copied ? 'Промт скопирован' : 'Скопировать промт' }}</button><span>Для преобразования списков нейросетью · {{ category.name }}</span></div>
      <div v-if="mode === 'import'" class="import-area"><label class="dropzone" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="dropped"><input type="file" accept=".txt,text/plain" class="sr-only" :disabled="busy" @change="upload($event.target.files[0])" /><span class="empty-icon"><Icon name="Upload" :size="27" /></span><strong>{{ busy ? 'Проверяем файл…' : 'Перетащите сюда текстовый файл' }}</strong><span>или <u>выберите на компьютере</u></span><small>.txt · UTF-8 · до 1 МБ · до 3000 заданий</small></label><div class="format-help"><h4><Icon name="Info" :size="15" />Формат: {{ category.name }}</h4><p>{{ category.help }}</p><pre>{{ category.sample }}</pre></div></div>
      <template v-else-if="mode === 'raw'">
        <div class="format-help mb-4"><p>{{ category.help }}</p><pre>{{ category.sample }}</pre></div>
        <div class="raw-editor"><div ref="rawNumbers" class="raw-line-numbers" aria-hidden="true"><div v-for="n in lineNumbers" :key="n">{{ n }}</div></div><textarea v-model="raw" class="input raw-input" wrap="off" spellcheck="false" :placeholder="category.sample" aria-label="Текст заданий с нумерацией строк" @scroll="rawNumbers.scrollTop = $event.target.scrollTop" @input="dirty = true"></textarea></div>
        <div class="raw-count">{{ lines }} заданий · одна строка — одно задание</div>
      </template>
      <template v-else>
        <div v-if="reviewCount" class="review-note"><Icon name="AlertCircle" :size="16" />В {{ reviewCount }} заданиях слово неизвестно или ударение неоднозначно. Укажите правильное ударение вручную: нажмите карандаш и выберите гласную.</div>
        <div class="builder"><div class="builder-title"><Icon :name="category.icon" :size="16" /><strong>{{ active ? `Редактирование задания №${active}` : 'Конструктор задания' }}</strong><button v-if="active" class="btn ghost sm ml-auto" @click="clearBuilder">Отмена</button></div>
          <div class="field"><label for="task-explanation">Пояснение / контекст (необязательно)</label><input id="task-explanation" v-model="explanation" class="input" placeholder="Например, песочный — для слова «замок»" maxlength="300" @input="dirty = true" /><span class="muted">Показывается над заданием. В тексте: [песочный] зАмок.</span></div>
          <template v-if="config.category === 'stress'"><div class="field"><label for="stress-word">Введите слово и нажмите на ударную гласную</label><input id="stress-word" v-model="word" class="input" placeholder="Например, каталог" @input="wordChanged" /></div><div v-if="word" class="letter-builder"><button v-for="(letter, i) in word" :key="i" :disabled="!vowels.includes(letter)" :class="{ vowel: vowels.includes(letter), chosen: stress === i }" :aria-label="`Ударение на ${letter}, буква ${i + 1}`" @click="stress = i">{{ letter + (stress === i ? '\u0301' : '') }}</button></div><p class="builder-tip">Гласные выделены голубым. Нажмите на ударную гласную.</p></template>
          <template v-else><div class="field"><label for="builder-text">{{ config.category === 'grammar' ? 'Текст предложения' : 'Слово или словосочетание' }}</label><textarea id="builder-text" ref="textInput" v-model="text" class="input" :placeholder="config.category === 'grammar' ? 'Введите предложение и поставьте курсор на место пропуска…' : 'Введите слово и выделите буквы для пропуска…'" @input="textChanged" @select="captureSelection" @click="captureSelection" @keyup="captureSelection"></textarea></div><div class="flex flex-wrap gap-2"><button class="btn secondary sm" @click="openGap(false)"><Icon name="Plus" :size="14" />{{ config.category === 'grammar' ? 'Вставить пропуск' : 'Добавить ложные варианты' }}</button><button v-if="config.category === 'spelling'" class="btn soft sm" @click="openGap(true)">+ Пропуск без буквы (∅)</button></div>
            <p v-if="config.category === 'spelling'" class="builder-tip">Пустое поле — без символа (∅), один пробел — пробел (␣). Не добавляйте пробелы после запятых для оформления.</p>
            <div v-for="(part, i) in parts.filter(p => 'options' in p)" :key="i" class="gap-editor"><div class="flex items-center justify-between gap-2"><span class="field-label">Пропуск {{ i + 1 }}</span><span class="badge green">Первый вариант — верный</span></div><div v-if="config.category === 'grammar'" class="field mt-3"><label>Начальная форма</label><input v-model="part.hint" class="input" placeholder="сберечь" /></div><div class="answer-tags"><span v-for="(option, j) in part.options" :key="j" :class="{ right: j === 0 }">{{ displayOption(option) }}<Icon v-if="j === 0" name="Check" :size="11" /></span></div><div class="gap-fields"><label>Верный ответ<input v-model="part.options[0]" class="input" placeholder="∅ — оставьте пустым" /></label><label>Ложные варианты через запятую<input class="input" :value="part.options.slice(1).join(',')" placeholder="Вариант,ещё вариант" @change="updateOptions(part, $event)" /></label></div><div v-if="config.category === 'spelling'" class="flex flex-wrap gap-2 mt-2"><button v-if="!part.options.includes('')" class="btn ghost sm" @click="part.options.push('')">+ Без символа (∅)</button><button v-if="!part.options.includes(' ')" class="btn ghost sm" @click="part.options.push(' ')">+ Пробел (␣)</button></div></div>
          </template>
          <div class="builder-footer"><button class="btn soft sm" :disabled="busy || (config.category === 'stress' ? !word || stress === null : !parts.some(p => 'options' in p))" @click="addRow"><Icon :name="active ? 'Check' : 'Plus'" :size="14" />{{ active ? 'Сохранить задание' : 'Добавить в список' }}</button></div>
        </div>
        <div v-if="selectionPopover" class="selection-popover" role="toolbar" aria-label="Действия с выделенными буквами"><span>«{{ text.slice(selection.start, selection.end) }}»</span><button class="btn soft sm" @mousedown.prevent @click="openGap(false)"><Icon name="Plus" :size="13" />Добавить ложные варианты</button><button class="icon-btn" aria-label="Скрыть подсказку" @click="selectionPopover = false"><Icon name="X" :size="13" /></button></div>
        <div class="editor-list-heading"><span>ЗАДАНИЯ В СПИСКЕ</span><span>{{ rows.length }}</span></div>
        <div v-if="duplicateIndexes.size" class="review-note" role="status"><Icon name="Copy" :size="16" />Повторяющиеся задания выделены жёлтым. Порядок ложных вариантов не учитывается.</div>
        <div v-if="!rows.length" class="builder-empty">Здесь появятся ваши задания. Добавьте первое выше или импортируйте файл.</div>
        <div class="editor-rows">
          <div v-for="(row, i) in rows" :key="i" class="editor-row" :class="{ reviewing: row.needs_review, editing: active === i + 1, duplicate: duplicateIndexes.has(i) }">
            <span class="row-number">{{ i + 1 }}</span><div class="flex-1 min-w-0"><TaskPreview :item="row" :category="config.category" /></div>
            <span v-if="duplicateIndexes.has(i)" class="badge amber">Повтор</span>
            <button class="icon-btn" :aria-label="`Редактировать задание ${i + 1}`" @click="editRow(row, i)"><Icon name="Pencil" :size="14" /></button><button class="icon-btn red" :aria-label="`Удалить задание ${i + 1}`" @click="removeRow(i)"><Icon name="Trash2" :size="14" /></button>
          </div>
        </div>
      </template>
      <div v-if="error" class="error-box mt-4" role="alert">{{ error }}</div>
    </div>
    <footer class="modal-footer"><span class="editor-save-note"><Icon name="ShieldCheck" :size="13" />Неизменённые задания сохранят прогресс</span><button class="btn secondary" :disabled="busy" @click="close">Отмена</button><button class="btn primary" :disabled="busy || loading || !name.trim() || (mode === 'raw' ? !raw.trim() : !rows.length)" @click="save"><Icon :name="busy ? 'LoaderCircle' : 'Check'" :class="{ spin: busy }" :size="16" />Сохранить список</button></footer>
    <div v-if="optionModal" class="gap-overlay"><div class="gap-dialog card"><h3>{{ config.category === 'grammar' ? 'Настройка пропуска' : 'Варианты написания' }}</h3><div v-if="config.category === 'grammar'" class="field mt-5"><label for="hint">Начальная форма (подсказка)</label><input id="hint" v-model="hint" class="input" placeholder="сберечь" /></div><div class="field mt-4"><label for="correct-option">Верный вариант</label><input id="correct-option" v-model="correct" class="input" :disabled="optionModal.empty" :placeholder="optionModal.empty ? '∅ — без символа' : 'Верный ответ'" /></div><div class="field"><label for="distractors">Ложные варианты через запятую</label><input id="distractors" v-model="distractors" class="input" placeholder="Например, и,е" /><span v-if="config.category === 'spelling'" class="muted">Пустой вариант — ∅; один пробел — ␣. Без пробелов для оформления.</span></div><div v-if="config.category === 'spelling'" class="flex flex-wrap gap-2 mb-4"><button v-if="!optionModal.empty" class="btn soft sm" @click="distractors += ','">+ Без символа (∅)</button><button class="btn soft sm" @click="distractors = distractors ? distractors + ', ' : ' '">+ Пробел (␣)</button><button v-if="!optionModal.empty" class="btn ghost sm" @click="correct = ' '">Верный ответ — пробел</button></div><div v-if="error" class="error-box mb-3">{{ error }}</div><div class="flex justify-end gap-2"><button class="btn secondary sm" @click="optionModal = null; error = ''">Отмена</button><button class="btn primary sm" :disabled="config.category === 'grammar' && (!hint.trim() || !correct.trim() || !distractors.trim())" @click="addGap">Добавить пропуск</button></div></div></div>
  </Modal>
</template>
<style scoped>
.prompt-toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0;color:#64748b}
.raw-editor{display:flex;height:340px;border:1px solid #dfe7f0;border-radius:9px;overflow:hidden}
.raw-line-numbers{flex-shrink:0;min-width:48px;padding:11px 10px;overflow:hidden;text-align:right;background:#f1f5f9;color:#64748b;user-select:none;font:15px/28px monospace}
.raw-editor .raw-input{border:0;border-radius:0;resize:none;min-height:0!important;height:100%;font:15px/28px monospace!important;padding:11px 13px;white-space:pre;overflow:auto}
.editor-rows .editor-row.duplicate { background: #fef3c7; }
.editor-row.duplicate.editing { box-shadow: inset 3px 0 #0284c7; }
.selection-popover{position:sticky;bottom:10px;z-index:2;display:flex;align-items:center;justify-content:center;gap:10px;width:fit-content;max-width:100%;margin:12px auto 0;padding:8px 10px;border:1px solid #d7e9f7;border-radius:12px;background:#fff;box-shadow:0 5px 20px #0f172a12}.selection-popover>span{font-size:11px;color:#7298b5;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.editor-toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:20px}.editor-toolbar .tabs button{padding:7px 10px;font-size:10px}.dropzone{display:flex;flex-direction:column;align-items:center;border:1px dashed #b9d8ee;border-radius:14px;background:#f7fbff;padding:35px 15px;cursor:pointer;color:#809bb2;gap:10px;text-align:center}.dropzone.dragging{background:#e4f3ff;border-color:#0284c7}.dropzone strong{color:#547c9c;font-size:13px;font-weight:500}.dropzone>span:not(.empty-icon){font-size:11px}.dropzone small{font-size:9px;color:#a0b0c1;margin-top:3px}.dropzone .empty-icon{width:53px;height:53px;margin-bottom:10px}.format-help{padding:15px;border:1px solid #e6eff8;border-radius:10px;background:#f8fbff;margin-top:16px}.format-help h4{display:flex;align-items:center;gap:7px;font-size:11px;color:#7098b7;margin-bottom:9px}.format-help p{font-size:10px;color:#8b9fb4;line-height:1.8}.format-help pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.9 monospace;margin:9px 0 0;color:#668aa9}.raw-input{min-height:280px!important;font-family:monospace!important;font-size:12px!important}.raw-count{font-size:10px;color:#9ba8b8;margin-top:8px}.review-note{display:flex;gap:8px;background:#fffbeb;border:1px solid #fef3c7;color:#b18b3a;border-radius:9px;padding:11px 13px;font-size:10px;line-height:1.7;margin-bottom:17px}.review-note svg{flex-shrink:0}.builder{border:1px solid #e3ecf5;border-radius:13px;padding:17px;background:#fbfdff}.builder-title{display:flex;gap:8px;align-items:center;color:#7497b4;margin-bottom:17px;font-size:11px;min-height:26px}.builder-title strong{font-weight:550}.letter-builder{display:flex;justify-content:center;gap:5px;flex-wrap:wrap;padding:10px 0 16px}.letter-builder button{border:1px solid transparent;background:transparent;font-size:28px;color:#71869c;width:34px;height:45px;position:relative;border-radius:8px;opacity:1}.letter-builder button.vowel{background:#edf6ff;color:#459acb;border-color:#dfedfa}.letter-builder button.chosen{background:#e2f8ef;color:#319677;border-color:#a9e5cd}.letter-accent{position:absolute;left:14px;top:0px}.builder-tip{font-size:9px;color:#a1b0c2;text-align:center;line-height:1.7}.builder-footer{display:flex;justify-content:flex-end;margin-top:16px;padding-top:13px;border-top:1px solid #eaf0f7}.gap-editor{padding:13px;background:#fff;border:1px solid #e5edf5;border-radius:9px;margin-top:13px}.answer-tags{display:flex;gap:5px;flex-wrap:wrap;margin:10px 0}.answer-tags span{display:flex;align-items:center;gap:5px;background:#fff4f5;border:1px solid #ffe2e7;color:#c57e8d;padding:4px 8px;border-radius:5px;font-size:11px}.answer-tags span.right{background:#effbf5;border-color:#d7f3e4;color:#4a9e7d}.gap-fields{display:grid;grid-template-columns:1fr 1.6fr;gap:10px}.gap-fields label{font-size:9px;color:#93a4b7;display:grid;gap:6px}.gap-fields .input{padding:8px 10px;font-size:11px}.editor-list-heading{display:flex;justify-content:space-between;font-size:9px;letter-spacing:1px;color:#91a2b5;font-weight:550;margin:23px 1px 12px}.editor-rows{border:1px solid #e9eff6;border-radius:10px;overflow:hidden}.editor-rows:empty{border:0}.editor-row{display:flex;align-items:center;gap:9px;border-bottom:1px solid #edf2f7;padding:11px 10px;font-size:13px}.editor-row:last-child{border:0}.editor-row.reviewing{background:#fffcf2}.editor-row.editing{background:#f0f8ff}.row-number{color:#b0bdcc;font-size:9px;width:18px;flex-shrink:0}.builder-empty{padding:20px;border:1px dashed #e2eaf3;border-radius:10px;text-align:center;color:#a0afc0;font-size:11px;line-height:1.8}.editor-save-note{margin-right:auto;font-size:9px;color:#9babbc;display:flex;align-items:center;gap:5px}.gap-overlay{position:fixed;inset:0;background:#0f253c30;backdrop-filter:blur(3px);display:flex;align-items:center;justify-content:center;padding:20px;z-index:1}.gap-dialog{width:390px;padding:24px;background:white;max-height:85vh;overflow:auto}@media(max-width:760px){.editor-save-note{display:none}.editor-toolbar .tabs button{font-size:9px;padding:6px 8px;gap:4px}.editor-toolbar .tabs button svg{display:none}.gap-fields{grid-template-columns:1fr}.letter-builder{gap:2px}.letter-builder button{width:29px;font-size:25px}.editor-row{gap:4px;padding:10px 7px}.editor-row .icon-btn{width:26px}}
</style>
