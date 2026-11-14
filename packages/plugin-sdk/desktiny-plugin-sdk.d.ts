// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
export interface DesktinyContext {
  place: 'case.side' | 'case.tab' | 'case.action' | 'task.side' | 'task.action' | 'home.widget' | 'page' | 'admin.page'
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
  /** Calls the plugin API; writes get an Idempotency-Key, an object body is sent as JSON. */
  api<T = unknown>(path: string, init?: Omit<RequestInit, 'body'> & { body?: BodyInit | object }): Promise<T>
  token(): Promise<DesktinySession>
  resize(height?: number): void
  /** A short notice under the plugin's name. */
  toast(text: string, tone?: 'success' | 'error'): void
  /** Go to a page of Desktiny (an in-app path such as "/cases/…"; anything else is ignored). */
  navigate(path: string): void
  /** Reload what Desktiny shows, after the plugin wrote to it. */
  refresh(): void
  /** End the dialog the frame runs in (case.action, task.action), handing back a result. */
  close(result?: unknown): void
  /** Ask the person in Desktiny's own dialog; true when they agree. */
  confirm(text: string): Promise<boolean>
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
