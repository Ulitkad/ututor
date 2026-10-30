import { describe, expect, it } from 'vitest'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import TaskPreview from './TaskPreview.vue'

describe('inline task preview', () => {
  it('renders the explanation between words in previews and results', async () => {
    const item = { data: { parts: [{ text: 'Установка  оборудования ' }, { hint: 'быть', options: ['была', 'был'], correct: 'была' }] },
      layout: [{ text: 'Установка ' }, { explanation: 'тест' }, { text: ' оборудования ' }, { gap: 0 }] }
    for (const solution of [false, true]) {
      const html = await renderToString(createSSRApp({ render: () => h(TaskPreview, { item, category: 'grammar', solution }) }))
      const text = html.replace(/<[^>]*>/g, '')
      expect(text).toContain('Установка [тест] оборудования ')
      expect(text).toContain(solution ? 'была' : 'быть → ')
      if (solution) expect(text).not.toContain('был |')
    }
  })
})
