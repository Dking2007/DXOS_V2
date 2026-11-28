// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// A task shown as a sheet of paper pinned to the board: a slight tilt of its own, the initials of who
// holds it, and an ink stamp when it is overdue or closed.
import type { Task } from '@dx/web-shared/types.ts'

/** Each sheet leans a little (−1.2° to 1.2°), always the same way for the same task. */
export function tilt(id: string): number {
  let hash = 0
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0
  return ((Math.abs(hash) % 25) - 12) / 10
}

/** "Nguyễn Thị Lan" → "NL"; a department or nobody gets its first letter or "?". */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return '?'
  const first = words[0][0]
  const last = words.length > 1 ? words[words.length - 1][0] : ''
  return (first + last).toLocaleUpperCase('vi')
}

export type StampTone = 'red' | 'green' | 'grey' | 'amber'

/** The ink stamp across a sheet, if any: closed beats overdue. */
export function stampOf(
  task: Pick<Task, 'status' | 'overdue'>,
): { label: string; tone: StampTone } | null {
  if (task.status === 'completed') return { label: 'Hoàn tất', tone: 'green' }
  if (task.status === 'cancelled') return { label: 'Đã hủy', tone: 'grey' }
  if (task.overdue) return { label: 'Quá hạn', tone: 'red' }
  if (task.status === 'returned') return { label: 'Trả lại', tone: 'amber' }
  return null
}
