// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// A small Markdown reader for assistant answers. It returns plain data that Vue renders as
// elements, so nothing the AI writes is ever inserted into the page as HTML.

export type Inline =
  | { t: 'text'; v: string }
  | { t: 'bold'; v: string }
  | { t: 'code'; v: string }
  | { t: 'link'; v: string; href: string }
  | { t: 'cite'; n: number }

export type Block =
  | { t: 'p'; inline: Inline[] }
  | { t: 'h'; inline: Inline[] }
  | { t: 'ul' | 'ol'; items: Inline[][] }
  | { t: 'code'; v: string }

const INLINE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(\[\d{1,2}\])|(https?:\/\/[^\s<>()"']+)/g

export function parseInline(text: string): Inline[] {
  const out: Inline[] = []
  let last = 0
  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0
    let token = match[0]
    if (match[4]) token = token.replace(/[.,;:!?]+$/, '')
    if (start > last) out.push({ t: 'text', v: text.slice(last, start) })
    if (match[1]) out.push({ t: 'code', v: token.slice(1, -1) })
    else if (match[2]) out.push({ t: 'bold', v: token.slice(2, -2) })
    else if (match[3]) out.push({ t: 'cite', n: Number(token.slice(1, -1)) })
    else out.push({ t: 'link', v: token, href: token })
    last = start + token.length
  }
  if (last < text.length) out.push({ t: 'text', v: text.slice(last) })
  return out
}

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d{1,3}[.)]\s+(.*)$/
const HEADING = /^\s*#{1,4}\s+(.*)$/

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = []
  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length) blocks.push({ t: 'p', inline: parseInline(paragraph.join('\n')) })
    paragraph = []
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.trim().startsWith('```')) {
      flush()
      const code: string[] = []
      while (++i < lines.length && !lines[i].trim().startsWith('```')) code.push(lines[i])
      blocks.push({ t: 'code', v: code.join('\n') })
      continue
    }
    if (!line.trim()) {
      flush()
      continue
    }
    const heading = HEADING.exec(line)
    if (heading) {
      flush()
      blocks.push({ t: 'h', inline: parseInline(heading[1]) })
      continue
    }
    const kind = BULLET.test(line) ? 'ul' : NUMBERED.test(line) ? 'ol' : null
    if (kind) {
      flush()
      const pattern = kind === 'ul' ? BULLET : NUMBERED
      const previous = blocks.at(-1)
      const list: Extract<Block, { t: 'ul' | 'ol' }> =
        previous && previous.t === kind ? previous : { t: kind, items: [] }
      if (list !== previous) blocks.push(list)
      list.items.push(parseInline(pattern.exec(line)![1]))
      continue
    }
    paragraph.push(line.trim())
  }
  flush()
  return blocks
}
