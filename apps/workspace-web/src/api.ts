// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { reactive } from 'vue'
import { createApi } from '@dx/web-shared/api.ts'

const base = createApi('workspace')

/** Requests waiting on an AI service, so the app can say it is still working when it is slow. */
export const aiActivity = reactive({ running: 0, since: 0 })
// Calls that go to a model; reading settings or the list of enabled features does not.
const AI_CALL = /^\/(ai\/(?!features|settings|index)|assistant\/(chat|models|providers\/[^/]+\/test))/

export function isAiCall(path: string, method = 'GET') {
  return method !== 'GET' && AI_CALL.test(path)
}

export const api = {
  ...base,
  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (!isAiCall(path, options.method)) return base.request<T>(path, options)
    if (!aiActivity.running) aiActivity.since = Date.now()
    aiActivity.running += 1
    try {
      return await base.request<T>(path, options)
    } finally {
      aiActivity.running -= 1
    }
  },
}
