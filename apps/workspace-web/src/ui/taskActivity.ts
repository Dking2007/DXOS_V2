// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// How a task's history reads as a workflow: each event becomes a step with a tone (moved forward,
// finished, held up, stopped, or a side note) and a short line of what changed.
import { formatDate } from '@dx/web-shared/api.ts'

export type StepTone = 'start' | 'progress' | 'done' | 'warn' | 'stop' | 'note'

export interface ActivityEvent {
  id: string
  action: string
  actor_name: string
  detail: Record<string, unknown>
  created_at: string
}

export interface ActivityStep {
  id: string
  action: string
  label: string
  tone: StepTone
  /** Main-path steps (created → … → done) get a full node; side notes get a small dot. */
  major: boolean
  actor: string
  at: string
  /** What changed, e.g. "Hạn: 12/11 → 15/11" or "+2 tệp". */
  note: string
  /** The reason someone gave, shown as a quote. */
  reason: string
}

const STEPS: Record<
  string,
  { label: string; tone: StepTone; major?: boolean }
> = {
  created: { label: 'Tạo công việc', tone: 'start', major: true },
  assigned: { label: 'Giao / phân công', tone: 'progress', major: true },
  accept: { label: 'Tiếp nhận', tone: 'progress', major: true },
  start: { label: 'Bắt đầu thực hiện', tone: 'progress', major: true },
  submit: { label: 'Nộp kết quả', tone: 'progress', major: true },
  complete: { label: 'Nghiệm thu hoàn tất', tone: 'done', major: true },
  return: { label: 'Trả lại', tone: 'warn', major: true },
  block: { label: 'Báo vướng mắc', tone: 'warn', major: true },
  unblock: { label: 'Tiếp tục xử lý', tone: 'progress', major: true },
  cancel: { label: 'Hủy việc', tone: 'stop', major: true },
  due_changed: { label: 'Đổi hạn', tone: 'warn' },
  automation_attached: { label: 'Gắn luồng tự động', tone: 'note' },
  automation_detached: { label: 'Gỡ luồng tự động', tone: 'note' },
  files_changed: { label: 'Cập nhật tài liệu đính kèm', tone: 'note' },
  updated: { label: 'Cập nhật', tone: 'note' },
}

const FIELD_NAMES: Record<string, string> = {
  title: 'tiêu đề',
  description: 'mô tả',
  priority: 'mức ưu tiên',
  due_at: 'hạn',
  watcher_ids: 'người theo dõi',
  checklist: 'checklist',
  labels: 'nhãn',
  file_ids: 'tệp đính kèm',
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function noteOf(event: ActivityEvent): string {
  const d = event.detail ?? {}
  switch (event.action) {
    case 'due_changed': {
      const from = text(d.from) ? formatDate(text(d.from), true) : 'không hạn'
      const to = text(d.to) ? formatDate(text(d.to), true) : 'không hạn'
      return `Hạn: ${from} → ${to}`
    }
    case 'files_changed': {
      const parts = []
      if (Number(d.added) > 0) parts.push(`+${Number(d.added)} tệp`)
      if (Number(d.removed) > 0) parts.push(`−${Number(d.removed)} tệp`)
      return parts.join(', ')
    }
    case 'automation_attached':
    case 'automation_detached':
      return text(d.name)
    case 'updated': {
      const fields = Array.isArray(d.fields)
        ? d.fields.map((f) => FIELD_NAMES[String(f)] ?? String(f))
        : []
      return fields.length ? `Sửa ${fields.join(', ')}` : ''
    }
    default:
      return ''
  }
}

export function toStep(event: ActivityEvent): ActivityStep {
  const known = STEPS[event.action]
  return {
    id: event.id,
    action: event.action,
    label: known?.label ?? event.action,
    tone: known?.tone ?? 'note',
    major: known?.major ?? false,
    actor: event.actor_name,
    at: event.created_at,
    note: noteOf(event),
    reason: text(event.detail?.reason),
  }
}

/** Newest last, as the work happened. With `limit`, the earlier ones are folded away. */
export function activitySteps(
  events: ActivityEvent[],
  limit?: number,
): { steps: ActivityStep[]; hidden: number } {
  const steps = events.map(toStep)
  if (!limit || steps.length <= limit + 1) return { steps, hidden: 0 }
  return { steps: steps.slice(-limit), hidden: steps.length - limit }
}

// ---- Drawing the history on a workflow canvas ------------------------------------------------

export type CanvasDirection = 'down' | 'right'

export interface PlacedStep {
  step: ActivityStep
  x: number
  y: number
  width: number
  height: number
  /** Last step of the whole history. */
  latest: boolean
}

export interface StepLink {
  id: string
  source: string
  target: string
  /** A side note hanging off a main step, drawn dashed. */
  aside: boolean
  tone: StepTone
  /** The main line wrapped to a new row: the link runs back along this height, between the rows. */
  corridor?: number
}

export const NODE_WIDTH = 236
export const GAP_RIGHT = 48
const GAP_DOWN = 26
const GAP_ASIDE = 18
const ROW_GAP = 64

/** Height a step needs: title and who/when, plus a line for what changed and two for a reason. */
export function stepHeight(step: ActivityStep): number {
  if (!step.major) return 48
  return 58 + (step.note ? 18 : 0) + (step.reason ? 36 : 0)
}

/** How many main steps fit side by side in a canvas this wide, at full size. */
export function stepsPerRow(width: number): number {
  return Math.max(1, Math.floor((width - 40 + GAP_RIGHT) / (NODE_WIDTH + GAP_RIGHT)))
}

/**
 * Where each step sits. `down` (the narrow card): every step in order, one under the other.
 * `right` (the wide view): main steps left to right, wrapping after `perRow` of them, side notes
 * stacked under the main step they followed, so the path of the work reads at a glance.
 */
export function canvasLayout(
  steps: ActivityStep[],
  direction: CanvasDirection,
  latestId = steps.at(-1)?.id,
  perRow = Infinity,
): { placed: PlacedStep[]; links: StepLink[] } {
  const placed: PlacedStep[] = []
  const links: StepLink[] = []
  const link = (from: ActivityStep, to: ActivityStep, aside: boolean, corridor?: number) =>
    links.push({ id: `${from.id}->${to.id}`, source: from.id, target: to.id, aside, tone: to.tone, corridor })
  const put = (step: ActivityStep, x: number, y: number) =>
    placed.push({ step, x, y, width: NODE_WIDTH, height: stepHeight(step), latest: step.id === latestId })

  if (direction === 'down') {
    let y = 0
    steps.forEach((step, index) => {
      put(step, 0, y)
      y += stepHeight(step) + GAP_DOWN
      if (index) link(steps[index - 1], step, !step.major || !steps[index - 1].major)
    })
    return { placed, links }
  }

  // Main steps open a column; side notes stack in the column of the main step before them.
  const columns: { main: ActivityStep; notes: ActivityStep[] }[] = []
  for (const step of steps) {
    if (step.major || !columns.length) columns.push({ main: step, notes: [] })
    else columns[columns.length - 1].notes.push(step)
  }
  let rowTop = 0
  let previous: ActivityStep | null = null
  for (let start = 0; start < columns.length; start += perRow) {
    const row = columns.slice(start, start + perRow)
    const mainHeight = Math.max(...row.map((c) => stepHeight(c.main)))
    let rowBottom = rowTop + mainHeight
    row.forEach((column, index) => {
      const x = index * (NODE_WIDTH + GAP_RIGHT)
      put(column.main, x, rowTop)
      if (previous) link(previous, column.main, false, index === 0 ? rowTop - ROW_GAP / 2 : undefined)
      previous = column.main
      let anchor = column.main
      let y = rowTop + mainHeight + GAP_ASIDE + 14
      for (const note of column.notes) {
        put(note, x, y)
        link(anchor, note, true)
        anchor = note
        y += stepHeight(note) + GAP_ASIDE
      }
      rowBottom = Math.max(rowBottom, y - GAP_ASIDE)
    })
    rowTop = rowBottom + ROW_GAP
  }
  return { placed, links }
}
