// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { InjectionKey, Ref } from 'vue'
import type { TriggerInfo } from './nodes'

export interface FlowContext {
  triggers: Ref<TriggerInfo[]>
  userName: (id: string) => string
  /** True while a test or a recorded run is painted on the canvas. */
  overlay: Ref<boolean>
  addAfter: (nodeId: string, handle?: string) => void
}
export const FLOW_CONTEXT: InjectionKey<FlowContext> = Symbol('flow-context')
