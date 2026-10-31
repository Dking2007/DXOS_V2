// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Which AI features the administrators switched on. Screens show their AI buttons only for
// those, so nobody meets a button that answers "not enabled".
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api'
import { useSession } from '../stores/session'

export type AiFeature =
  | 'case_extract'
  | 'case_summary'
  | 'case_check'
  | 'decision_draft'
  | 'document_draft'
  | 'document_qa'
  | 'semantic_search'
  | 'file_labels'
  | 'task_parse'
  | 'task_breakdown'
  | 'daily_digest'
  | 'report_narrative'
  | 'chat_summary'
  | 'writing_help'
  | 'automation_ai'
  | 'assistant_my_data'
  | 'package_scenarios'

interface AiStatus {
  enabled: AiFeature[]
  semantic_ready: boolean
  remaining: number | null
}

export function useAi() {
  const session = useSession()
  const status = useQuery({
    queryKey: ['ai-features'],
    queryFn: () => api.request<AiStatus>('/ai/features'),
    enabled: computed(() => !!session.user),
    staleTime: 60_000,
  })
  return {
    status,
    on: (feature: AiFeature) => !!status.data.value?.enabled.includes(feature),
    semanticReady: computed(() => !!status.data.value?.semantic_ready),
  }
}
