// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Steps offered by switched-on connected plugins. Each becomes a `plugin_action` node whose settings
// form is drawn from the plugin's own `config_schema`; the plugin does the work on its server.
import { useQuery } from '@tanstack/vue-query'
import { api } from '../api'

export interface PluginField {
  type: 'string' | 'number' | 'boolean'
  title: string
  description?: string
  enum?: string[] | null
  default?: unknown
}
export interface PluginStep {
  plugin_id: string
  plugin_name: string
  kind: string
  title: string
  description: string
  config_schema: { properties: Record<string, PluginField>; required: string[] }
  outputs: Record<string, string>
  mode?: 'sync' | 'async'
  timeout_days?: number | null
}

export function usePluginSteps() {
  return useQuery({
    queryKey: ['plugin-steps'],
    queryFn: () => api.request<{ items: PluginStep[] }>('/plugins/nodes').then((result) => result.items),
    staleTime: 60_000,
  })
}

/** The settings a new step starts with: the plugin's defaults, and what it returns for later steps. */
export function pluginStepConfig(step: PluginStep): Record<string, unknown> {
  const config = Object.fromEntries(
    Object.entries(step.config_schema.properties)
      .filter(([, field]) => field.default !== undefined && field.default !== null)
      .map(([key, field]) => [key, field.default]),
  )
  return {
    plugin_id: step.plugin_id,
    node: step.kind,
    title: step.title,
    config,
    outputs: { ...step.outputs },
    // A long-running step may also end on "timeout"; the canvas offers that exit.
    ...(step.mode === 'async' ? { mode: 'async' } : {}),
  }
}
