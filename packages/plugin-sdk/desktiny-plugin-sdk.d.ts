// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
export interface DesktinyContext {
  place: 'case.side' | 'task.side' | 'home.widget' | 'page'
  plugin_id: string
  record: { case_id?: string; task_id?: string }
  viewer: { id: string; display_name: string } | null
  theme: 'light' | 'dark'
  colors: Record<string, string>
  font: string
  app: { name: string; org: string }
}
export interface DesktinySession {
  token: string
  expires_at: string
  api_base: string
}
export interface DesktinyConnection {
  context: Promise<DesktinyContext>
  api<T = unknown>(path: string, init?: RequestInit): Promise<T>
  token(): Promise<DesktinySession>
  resize(height?: number): void
  refreshContext(): void
}
export function connect(options?: {
  desktinyOrigin?: string
  autoResize?: boolean
  onContext?: (context: DesktinyContext) => void
}): DesktinyConnection
export function applyTheme(context: DesktinyContext): void
export const PROTOCOL: 1
declare const DesktinyPlugin: { connect: typeof connect; applyTheme: typeof applyTheme; PROTOCOL: 1 }
export default DesktinyPlugin
