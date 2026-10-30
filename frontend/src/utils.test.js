import { describe, expect, it } from 'vitest'
import { addRandom, displayOption, percentage, shuffle, taskLabel } from './utils'

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
  })
  it('handles empty progress and Russian plural forms', () => {
    expect(percentage(0, 0)).toBe(0)
    expect(percentage(42, 120)).toBe(35)
    expect([1, 2, 11, 21, 24].map(taskLabel)).toEqual(['задание', 'задания', 'заданий', 'задание', 'задания'])
  })
})
