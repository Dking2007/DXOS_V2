// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { MeOverview } from '@dx/web-shared/types.ts'
import { api } from '../api'
import { useSession } from '../stores/session'

// One shared query feeds the menu badges, the bottom bar and the home agenda.
export function useOverview() {
  const session = useSession()
  return useQuery({
    queryKey: ['me-overview'],
    queryFn: () => api.request<MeOverview>('/me/overview'),
    enabled: computed(() => !!session.user),
    refetchInterval: 30_000,
  })
}
