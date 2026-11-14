// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Ready-made processes come from installed sector packs (the core pack `desktiny.core` holds the
// stock ones), so an organisation's pack can add its own to the "new process" dialog.
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api'
import type { ApiGraph } from './nodes'

export interface PackTemplate {
  key: string
  pack_id: string
  pack_name: string
  title: string
  description: string
  graph: ApiGraph
}

export function fetchPackTemplates() {
  return api.request<{ items: PackTemplate[] }>('/packs/templates').then((result) => result.items)
}

export function usePackTemplates() {
  return useQuery({ queryKey: ['pack-templates'], queryFn: fetchPackTemplates, staleTime: 60_000 })
}
