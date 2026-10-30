export const categories = [
  { id: 'stress', name: 'Орфоэпия', description: 'Ударения и произношение', icon: 'AudioLines', short: 'Ударения', sample: 'дЕрево\nкаталОг\n[песочный] зАмок\nзамОк [дверной]\nА́рка', help: 'Одно русское слово на строке. Ударная гласная — заглавная; для первой буквы добавьте знак ударения: А́рка. Пояснение в квадратных скобках может стоять в любом месте: [песочный] зАмок, зАмок [песочный] или зА[песочный]мок. Оно показывается отдельно и не является частью ответа. Пояснений может быть несколько, вложенные скобки не допускаются. Слова без явного ударения проверяются автоматически; неоднозначные требуют ручной проверки.' },
  { id: 'spelling', name: 'Орфография', description: 'Буквы на своих местах', icon: 'SpellCheck', short: 'Правописание', sample: 'Ж(е,и)лезо\nт(е,)ст\nграм(,м)ота [без удвоения]\nПо( ,)этому\n[значит «потому»] По(, )этому\nс(ло,ла)в(о,а,и,е)', help: 'Одна строка — одно задание. В скобках варианты через запятую, первый всегда верный. Пустой вариант — отсутствие символа: т(е,)ст или грам(,м)ота. Один пробел — настоящий пробел: По( ,)этому (раздельно), По(, )этому (слитно). Не добавляйте пробелы после запятых для оформления! Пропусков может быть несколько. Пояснение [контекст] может стоять в любом месте задания, в том числе внутри слова; оно не входит в ответ. После верного пустого ответа слово отображается без ∅.' },
  { id: 'grammar', name: 'Грамматические нормы', description: 'Формы слов в контексте', icon: 'TextCursorInput', short: 'Грамматика', sample: 'Установка оборудования для фильтрации воды в будущем (сберечь|сбережет,сберегет,сберечет,сбережгет) здоровье жителей города.', help: 'Одна строка — одно задание. В скобках до | — начальная форма, после | — варианты через запятую. Первый вариант верный. Можно несколько пропусков. Варианты непустые, без повторов; вложенные скобки не допускаются. Пояснение [контекст] можно вставить в любом месте предложения; оно не является частью ответа: Он (сберечь|сбережёт,сберегёт) здоровье [о будущем].' },
]
export const categoryById = id => categories.find(c => c.id === id) || categories[0]
export const vowels = 'аеёиоуыэюя'
export const displayOption = value => value === '' ? '∅' : value === ' ' ? '␣' : value
export const normalizeOption = value => value && /^\s+$/.test(value) ? ' ' : value.trim()
export function serializeTask(data, category) {
  const prefix = data.explanation ? `[${data.explanation}] ` : ''
  if ('word' in data) return prefix + [...data.word].map((c, i) => i === data.stress ? c.toUpperCase() + (i === 0 ? '\u0301' : '') : c).join('')
  return prefix + data.parts.map(p => 'text' in p ? p.text : `(${category === 'grammar' ? `${p.hint}|` : ''}${p.options.join(',')})`).join('')
}
export function importPrompt(id) {
  const category = categoryById(id)
  return `Преобразуй приведённый ниже материал в формат импорта uTutor. Тип заданий: ${category.name}.\nВерни только готовый текст: без Markdown, нумерации, заголовков и комментариев. Одна строка — одно задание. Не более 3000 строк. Сохраняй ё, контекст и правильные ответы. Не выдумывай спорные ответы: если данных недостаточно, сначала запроси уточнение.\n${category.help}\n${id === 'grammar' ? 'Формат: текст (начальная форма|правильная словоформа,неправильная словоформа). Нужно минимум два разных непустых варианта. Можно несколько пропусков. Пояснение [контекст] может стоять в любом месте строки.' : id === 'stress' ? 'Ровно одна отмеченная ударная гласная в каждом слове. Пояснения не должны содержать квадратные скобки внутри.' : 'Минимум два разных варианта в каждом пропуске. Не используй вложенные скобки. Строго различай пустую строку и один пробел в вариантах. Не обозначай отсутствие символа знаками ∅, Ø или подчёркиванием.'}\nПримеры:\n${category.sample}\n\nМатериал для преобразования:\n[вставьте свой список]`
}
export function shuffle(items, random = Math.random) {
  const copy = [...items]
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1)); [copy[i], copy[j]] = [copy[j], copy[i]]
  }
  return copy
}
export function addRandom(items, selected, count) {
  return new Set([...selected, ...shuffle(items.filter(i => !selected.has(i.id) && !i.needs_review && i.status !== 'correct')).slice(0, count).map(i => i.id)])
}
export function duplicateRowIndexes(rows) {
  const normalize = value => value.normalize('NFC').toLowerCase().replace(/\s+/g, ' ').trim()
  const groups = new Map()
  rows.forEach((row, index) => {
    const data = row.data
    // Keep the correct answer distinct, but ignore the order of distractors.
    const optionKey = value => value === ' ' ? '\\SPACE' : normalize(value)
    const key = JSON.stringify([normalize(data.explanation || ''), 'word' in data ? normalize(data.word) : data.parts.map(part =>
      'text' in part ? ['text', normalize(part.text)] : ['gap', normalize(part.hint), optionKey(part.correct), part.options.map(optionKey).sort()]
    )])
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(index)
  })
  return new Set([...groups.values()].filter(indexes => indexes.length > 1).flat())
}
export function percentage(correct, total) { return total ? Math.round(correct / total * 100) : 0 }
export function initials(name) { return name.split(/\s+/).slice(0, 2).map(s => s[0]).join('').toUpperCase() }
export function taskLabel(count) {
  const n = count % 100
  return n >= 11 && n <= 14 ? 'заданий' : count % 10 === 1 ? 'задание' : count % 10 >= 2 && count % 10 <= 4 ? 'задания' : 'заданий'
}
