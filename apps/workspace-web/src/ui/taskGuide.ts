// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Where a task stands and what the person looking at it should do next, in plain words.

export const TASK_STAGES = ['Đã giao', 'Tiếp nhận', 'Đang làm', 'Chờ nghiệm thu', 'Hoàn tất'] as const

/** The stage reached: the index into TASK_STAGES; -1 for a cancelled task. */
export function taskStage(status: string): number {
  return (
    {
      draft: 0,
      assigned: 0,
      accepted: 1,
      in_progress: 2,
      blocked: 2,
      returned: 2,
      submitted: 3,
      completed: 4,
    } as Record<string, number>
  )[status] ?? (status === 'cancelled' ? -1 : 0)
}

/** "Còn 2 ngày", "Quá hạn 3 giờ", or nothing without a deadline or once the work is done. */
export function dueText(due: string | null | undefined, status: string, now = Date.now()): string {
  if (!due || ['completed', 'cancelled'].includes(status)) return ''
  const minutes = Math.round((new Date(due).getTime() - now) / 60000)
  const size = Math.abs(minutes)
  const amount = size >= 1440 ? `${Math.round(size / 1440)} ngày` : size >= 60 ? `${Math.round(size / 60)} giờ` : `${Math.max(size, 1)} phút`
  return minutes < 0 ? `Quá hạn ${amount}` : `Còn ${amount}`
}

export interface GuideInput {
  status: string
  isAssignee: boolean
  canManage: boolean
  hasAssignee: boolean
  /** Reason given when it was last returned or blocked, if any. */
  reason?: string
  requiredFiles?: number
  fileCount?: number
  overdue?: boolean
}

/** One sentence on what happens next, for the person looking. */
export function nextStep(input: GuideInput): { tone: 'info' | 'warn' | 'done'; text: string } {
  const { status, isAssignee, canManage, hasAssignee, reason } = input
  const files =
    input.requiredFiles && (input.fileCount ?? 0) < input.requiredFiles
      ? ` Việc này cần ít nhất ${input.requiredFiles} tệp kết quả ở mục Tài liệu.`
      : ''
  const why = reason ? ` Lý do: “${reason}”.` : ''
  if (status === 'completed') return { tone: 'done', text: 'Việc đã được nghiệm thu và hoàn tất.' }
  if (status === 'cancelled') return { tone: 'done', text: `Việc đã bị hủy.${why}` }
  if (!hasAssignee)
    return { tone: 'info', text: 'Việc đang chờ trưởng đơn vị phân công cho một người cụ thể.' }
  if (isAssignee) {
    if (status === 'assigned') return { tone: 'info', text: 'Việc đang chờ bạn. Bấm Tiếp nhận để nhận việc.' }
    if (status === 'returned')
      return { tone: 'warn', text: `Việc bị trả lại để làm tiếp.${why} Sửa xong thì nộp lại kết quả.${files}` }
    if (status === 'blocked')
      return { tone: 'warn', text: `Bạn đã báo vướng mắc.${why} Khi gỡ được, bấm Tiếp tục.` }
    if (status === 'submitted') return { tone: 'info', text: 'Bạn đã nộp kết quả. Đang chờ người giao nghiệm thu.' }
    return { tone: 'info', text: `Làm xong thì cập nhật checklist, đính kèm kết quả và bấm Nộp kết quả.${files}` }
  }
  if (canManage) {
    if (status === 'submitted')
      return { tone: 'warn', text: 'Người làm đã nộp kết quả. Kiểm tra rồi bấm Nghiệm thu, hoặc Trả lại kèm lý do.' }
    if (status === 'blocked') return { tone: 'warn', text: `Người làm đang gặp vướng mắc.${why}` }
    if (input.overdue)
      return { tone: 'warn', text: 'Việc đã quá hạn. Bạn có thể trao đổi với người làm hoặc đổi hạn kèm lý do.' }
    if (status === 'assigned') return { tone: 'info', text: 'Đang chờ người nhận tiếp nhận việc.' }
    return { tone: 'info', text: 'Người làm đang thực hiện. Bạn sẽ được báo khi có kết quả.' }
  }
  return { tone: 'info', text: 'Bạn đang theo dõi việc này.' }
}
