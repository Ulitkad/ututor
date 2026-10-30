import { describe, expect, it } from 'vitest'
import { addRandom, displayOption, duplicateRowIndexes, importPrompt, normalizeOption, percentage, serializeTask, shuffle, stressLetters, taskEditor, taskLabel, taskSegments } from './utils'

describe('training helpers', () => {
  it('adds random unselected tasks without dropping existing selection', () => {
    const items = Array.from({ length: 50 }, (_, id) => ({ id }))
    const selected = new Set([0, 1, 2])
    const result = addRandom(items, selected, 20)
    expect(result.size).toBe(23)
    expect([...selected].every(id => result.has(id))).toBe(true)
    expect(selected.size).toBe(3)
  })
  it('handles exhausted selection and excludes unreviewed tasks', () => {
    expect([...addRandom([{ id: 1 }, { id: 2, needs_review: true }], new Set([1]), 50)]).toEqual([1])
  })
  it('adds only new tasks and mistakes, even when fewer than requested remain', () => {
    const items = [{ id: 1, status: 'correct' }, { id: 2, status: 'new' }, { id: 3, status: 'mistake' }, { id: 4, status: 'new', needs_review: true }]
    const selected = new Set()
    const result = addRandom(items, selected, 10)
    expect([...result].sort()).toEqual([2, 3])
    expect([...addRandom(items, result, 10)].sort()).toEqual([2, 3])
    expect(selected.size).toBe(0)
    expect(addRandom(items, new Set([1]), 10).has(1)).toBe(true)
    expect(addRandom([items[0]], new Set(), 10).size).toBe(0)
  })
  it('shuffles without mutating or losing items', () => {
    const original = [1, 2, 3, 4]
    const result = shuffle(original, () => 0)
    expect(result).not.toEqual(original)
    expect([...result].sort()).toEqual(original)
    expect(original).toEqual([1, 2, 3, 4])
  })
  it('always renders empty answers explicitly', () => {
    expect(displayOption('')).toBe('∅')
    expect(displayOption('ь')).toBe('ь')
    expect(displayOption(' ')).toBe('␣')
  })
  it('handles empty progress and Russian plural forms', () => {
    expect(percentage(0, 0)).toBe(0)
    expect(percentage(42, 120)).toBe(35)
    expect([1, 2, 11, 21, 24].map(taskLabel)).toEqual(['задание', 'задания', 'заданий', 'задание', 'задания'])
  })
})

describe('import format v2', () => {
  it('round-trips inline explanations through the visual grammar editor', () => {
    const source = 'Установка [тест] оборудования ▢. [конец]'
    const item = { source: source.replace('▢', '(сберечь|сбережёт,сберегёт)'), data: { parts: [{ hint: 'сберечь', options: ['сбережёт', 'сберегёт'], correct: 'сбережёт' }] } }
    const editor = taskEditor(item, 'grammar')
    expect(editor.text).toBe(source)
    expect(serializeTask(editor, 'grammar')).toBe(item.source)
    editor.parts[0].text = 'Монтаж [тест] оборудования '
    expect(serializeTask(editor, 'grammar')).toContain('Монтаж [тест] оборудования (')
  })
  it('preserves explanations within gap options and punctuation', () => {
    const source = '[а, б|в] грам(,[без, удвоения]м)ота [конец]'
    const item = { source, data: { parts: [{ hint: '', options: ['', 'м'], correct: '' }] } }
    expect(serializeTask(taskEditor(item, 'spelling'), 'spelling')).toBe(source)
    const grammar = { source: 'Он (быть[глагол]|был[м, ж],была).', data: { parts: [{ hint: 'быть', options: ['был', 'была'] }] } }
    expect(serializeTask(taskEditor(grammar, 'grammar'), 'grammar')).toBe(grammar.source)
  })
  it.each(['[Песочный] зАмок', 'зА[Песочный]мок', 'зАмок [Песочный]'])('keeps stress indexes and annotation case: %s', source => {
    const editor = taskEditor({ source, data: { word: 'замок', stress: 1 } }, 'stress')
    expect(serializeTask({ word: editor.word, stress: 1 }, 'stress')).toBe(source)
    expect(stressLetters(editor.word).filter(p => 'letter' in p).map(p => p.letter)).toEqual([0, 1, 2, 3, 4])
  })
  it('resolves public layout without changing gap indexes', () => {
    const parts = [{ text: 'По' }, { options: [' ', ''] }, { text: 'этому' }]
    const segments = taskSegments({ parts, layout: [{ text: 'По' }, { explanation: 'контекст' }, { gap: 0 }, { text: 'этому' }] })
    expect(segments[1]).toEqual({ explanation: 'контекст' })
    expect(segments[2]).toEqual({ gap: 0, part: parts[1] })
  })
  it('distinguishes spaces, omission and padded letters', () => {
    expect(['', ' ', '  ', ' е '].map(normalizeOption)).toEqual(['', ' ', ' ', 'е'])
    const data = { explanation: 'контекст', parts: [{ text: 'По' }, { hint: '', options: [' ', ''], correct: ' ' }, { text: 'этому' }] }
    expect(serializeTask(data, 'spelling')).toBe('[контекст] По( ,)этому')
    expect(serializeTask({ word: 'замок', stress: 1, explanation: 'песочный' }, 'stress')).toBe('[песочный] зАмок')
    expect(serializeTask({ word: 'арка', stress: 0 }, 'stress')).toBe('А́рка')
  })
  it('provides distinct prompts with category rules', () => {
    const prompts = ['stress', 'spelling', 'grammar'].map(importPrompt)
    expect(new Set(prompts).size).toBe(3)
    expect(prompts[0]).toContain('[песочный] зАмок')
    expect(prompts[1]).toContain('По( ,)этому')
    expect(prompts[2]).toContain('начальная форма|')
    expect(prompts.every(prompt => prompt.includes('в любом месте'))).toBe(true)
  })
  it('does not confuse homographs with different explanations or spaces with omissions', () => {
    expect(duplicateRowIndexes([
      { data: { word: 'замок', stress: 1, explanation: 'песочный' } },
      { data: { word: 'замок', stress: 3, explanation: 'дверной' } },
      ...[['', 'т'], [' ', 'т']].map(options => ({ data: { parts: [{ hint: '', options, correct: options[0] }] } })),
    ]).size).toBe(0)
  })
})

describe('duplicate tasks', () => {
  const word = (value, stress = null) => ({ data: { word: value, stress } })
  const gap = (options, hint = '') => ({ hint, options, correct: options[0] })
  const task = parts => ({ data: { parts } })

  it('highlights every occurrence of a repeated word', () => {
    expect([...duplicateRowIndexes([word('каталог', 5), word('звонит', 4), word('Каталог', 5), word('каталог')])]).toEqual([0, 2, 3])
  })
  it('ignores spelling distractor order, including empty options and multiple gaps', () => {
    const rows = [
      task([{ text: 'ж' }, gap(['е', 'и', 'а']), { text: 'лезо' }]),
      task([{ text: 'ж' }, gap(['е', 'а', 'и']), { text: 'лезо' }]),
      task([{ text: 'опас' }, gap(['', 'т']), { text: 'ный' }, gap(['ь', '', 'ъ'])]),
      task([{ text: 'опас' }, gap(['', 'т']), { text: 'ный' }, gap(['ь', 'ъ', ''])]),
    ]
    expect([...duplicateRowIndexes(rows)]).toEqual([0, 1, 2, 3])
  })
  it('recognizes grammar sentences with reordered distractors', () => {
    const sentence = options => task([{ text: 'Он ' }, gap(options, 'сберечь'), { text: ' здоровье.' }])
    expect([...duplicateRowIndexes([
      sentence(['сбережёт', 'сберегёт', 'сберечёт']),
      sentence(['сбережёт', 'сберечёт', 'сберегёт']),
    ])]).toEqual([0, 1])
  })
  it('does not confuse different text, hints, correct answers or option sets', () => {
    expect(duplicateRowIndexes([
      task([{ text: 'ж' }, gap(['е', 'и', 'а']), { text: 'лезо' }]),
      task([{ text: 'ж' }, gap(['и', 'е', 'а']), { text: 'лезо' }]),
      task([{ text: 'ж' }, gap(['е', 'и']), { text: 'лезо' }]),
      task([{ text: 'ж' }, gap(['е', 'и', 'а'], 'подсказка'), { text: 'лезо' }]),
      task([{ text: 'ж' }, gap(['е', 'и', 'а']), { text: 'леза' }]),
    ]).size).toBe(0)
  })
  it('clears the highlight after removing or editing a duplicate', () => {
    const rows = [word('каталог'), word('каталог')]
    expect(duplicateRowIndexes(rows).size).toBe(2)
    rows[1] = word('звонит')
    expect(duplicateRowIndexes(rows).size).toBe(0)
    expect(duplicateRowIndexes(rows.slice(0, 1)).size).toBe(0)
    expect(duplicateRowIndexes([]).size).toBe(0)
  })
})
