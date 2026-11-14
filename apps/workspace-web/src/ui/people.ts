// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Profile photos by person, from the shared directory; your own comes from the session so a new
// photo shows at once.
import { computed } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import type { Page } from '@dx/web-shared/api.ts'
import type { User } from '@dx/web-shared/types.ts'
import { api } from '../api'
import { useSession } from '../stores/session'

export function usePhotos() {
  const session = useSession()
  const users = useQuery({
    queryKey: ['users'],
    queryFn: () => api.request<Page<User>>('/users'),
    staleTime: 60_000,
  })
  const byId = computed(() => {
    const map = new Map<string, string>()
    for (const user of users.data.value?.items ?? [])
      if (user.avatar_url) map.set(user.id, user.avatar_url)
    const me = session.user
    if (me) {
      if (me.avatar_url) map.set(me.id, me.avatar_url)
      else map.delete(me.id)
    }
    return map
  })
  return (id: string | null | undefined) =>
    id ? (byId.value.get(id) ?? null) : null
}

/** Up to two letters for someone without a photo: "Nguyễn Văn An" becomes "VA". */
export function initialsOf(name: string | null | undefined): string {
  return (name ?? '')
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((word) => word[0] ?? '')
    .join('')
    .toUpperCase()
}
