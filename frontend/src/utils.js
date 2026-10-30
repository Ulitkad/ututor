export const categories = [
  { id: 'stress', name: 'Орфоэпия', description: 'Ударения и произношение', icon: 'AudioLines', short: 'Ударения', sample: 'дЕрево\nсобАка\nкаталОг\nзвонИт', help: 'Одно слово на строке. Ударную гласную можно отметить заглавной буквой. Неизвестные слова и омографы потребуют проверки.' },
  { id: 'spelling', name: 'Орфография', description: 'Буквы на своих местах', icon: 'SpellCheck', short: 'Правописание', sample: 'Ж(е,и)лезо\nПам(я,и)ть\nмыш(ь, )\nопас( ,т)ный\nс(ло,ла)в(о,а,и,е)', help: 'В скобках — варианты через запятую. Первый всегда верный. Пустой вариант или пробел означает «без буквы» (∅). Пропусков может быть несколько.' },
  { id: 'grammar', name: 'Грамматические нормы', description: 'Формы слов в контексте', icon: 'TextCursorInput', short: 'Грамматика', sample: 'Установка оборудования для фильтрации воды в будущем (сберечь|сбережет,сберегет,сберечет,сбережгет) здоровье жителей города.', help: 'В скобках до | — начальная форма. После | — варианты через запятую. Первый вариант верный.' },
]
export const categoryById = id => categories.find(c => c.id === id) || categories[0]
export const vowels = 'аеёиоуыэюя'
export const displayOption = value => value === '' ? '∅' : value
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
    const key = JSON.stringify('word' in data ? normalize(data.word) : data.parts.map(part =>
      'text' in part ? ['text', normalize(part.text)] : ['gap', normalize(part.hint), normalize(part.correct), part.options.map(normalize).sort()]
    ))
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
