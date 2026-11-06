// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// A step's deadline is stored in hours; people read and type it in days when it is whole days.

export function deadlineParts(hours: number | null | undefined): { amount: number; unit: 1 | 24 } {
  if (!hours) return { amount: 0, unit: 24 }
  return hours % 24 === 0 ? { amount: hours / 24, unit: 24 } : { amount: hours, unit: 1 }
}

export function deadlineText(hours: number | null | undefined): string {
  if (!hours) return 'Không giới hạn thời gian'
  const { amount, unit } = deadlineParts(hours)
  return `Trong ${amount} ${unit === 24 ? 'ngày' : 'giờ'}`
}
