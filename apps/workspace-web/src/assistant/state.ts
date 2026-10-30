// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { ref } from 'vue'

/** Whether the assistant panel is open; the command palette can open it from anywhere. */
export const assistantOpen = ref(false)

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  sources?: { n: number; id: string; title: string; category: string }[]
  truncated?: boolean
}

/** The turns sent with a question: the recent conversation, trimmed to what the API accepts. */
export function historyFor(turns: ChatTurn[], limit = 12): { role: ChatTurn['role']; content: string }[] {
  const recent = turns.slice(-limit)
  // The API needs the history to start with a question.
  while (recent.length && recent[0].role !== 'user') recent.shift()
  return recent.map((turn) => ({ role: turn.role, content: turn.content.slice(0, 4000) }))
}
