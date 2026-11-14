// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { ref } from 'vue'
import type { AssistantItem } from '@dx/web-shared/types.ts'

/** Whether the assistant panel is open; the command palette can open it from anywhere. */
export const assistantOpen = ref(false)

/** The dossier on screen, when its page lets people ask the AI about it ("Trợ lý công việc"). */
export interface CaseContext {
  id: string
  title: string
  suggestions: string[]
}
export const caseContext = ref<CaseContext | null>(null)
export const assistantTab = ref<'general' | 'case'>('general')
/** A question picked on the dossier page, asked as soon as the dossier tab shows. */
export const pendingCaseQuestion = ref('')

/** Open the assistant on the dossier tab, optionally asking a question straight away. */
export function askAboutCase(question = '') {
  assistantTab.value = 'case'
  pendingCaseQuestion.value = question.trim()
  assistantOpen.value = true
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  sources?: { n: number; id: string; title: string; category: string }[]
  items?: AssistantItem[]
  tools?: { plugin_id: string; plugin: string; tool: string }[]
  truncated?: boolean
}

/** "@3" in an answer: a reference to one of the asker's items, valid only for that answer. */
export const REF = /(?<![\w@])@(\d{1,3})(?!\d)/g

/** The turns sent with a question: the recent conversation, trimmed to what the API accepts. */
export function historyFor(turns: ChatTurn[], limit = 12): { role: ChatTurn['role']; content: string }[] {
  const recent = turns.slice(-limit)
  // The API needs the history to start with a question.
  while (recent.length && recent[0].role !== 'user') recent.shift()
  // References are numbered afresh for every question, so old ones would point at the wrong item.
  return recent.map((turn) => ({
    role: turn.role,
    content: (turn.role === 'assistant' ? turn.content.replace(REF, '').replace(/ {2,}/g, ' ') : turn.content).slice(
      0,
      4000,
    ),
  }))
}
