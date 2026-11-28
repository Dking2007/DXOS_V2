// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { onBeforeUnmount, onMounted, toValue, type MaybeRefOrGetter } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { confirmDialog } from '@dx/web-shared/confirm.ts'

export const DISCARD_QUESTION = 'Bạn có thay đổi chưa lưu. Rời đi và bỏ các thay đổi này?'
const askDiscard = (message: string) => confirmDialog({ message, confirmLabel: 'Bỏ thay đổi', danger: true })
export const LOGOUT_QUESTION = 'Bạn có thay đổi chưa lưu. Đăng xuất và bỏ các thay đổi này?'

// Every mounted guard, so actions outside the page (logging out) can ask first.
const sources = new Set<() => boolean>()
// Set once the person agreed to throw the edits away, so the same leave is not asked twice
// (once by us, then again by the browser's own "leave site?" prompt).
let released = false

export function registerDirty(source: () => boolean) {
  sources.add(source)
  return () => {
    sources.delete(source)
  }
}

export function hasUnsavedChanges() {
  for (const source of sources) if (source()) return true
  return false
}

/** Asks once for everything open on screen; once agreed, the page guards let the leave through. */
export async function confirmLeaveAll(question = DISCARD_QUESTION) {
  if (released || !hasUnsavedChanges()) return true
  if (!(await askDiscard(question))) return false
  released = true
  return true
}

/** The leave did not happen after all (e.g. logging out failed): guard the edits again. */
export function resetLeaveConsent() {
  released = false
}

// Asks before throwing away edits: on navigation, tab close/reload, and (via
// confirmDiscard) when a dialog holding a form is closed.
export function useUnsavedGuard(dirty: MaybeRefOrGetter<boolean>) {
  const guarded = () => !released && toValue(dirty)
  let unregister = () => {}
  function beforeUnload(event: BeforeUnloadEvent) {
    if (!guarded()) return
    event.preventDefault()
    event.returnValue = ''
  }
  onMounted(() => {
    unregister = registerDirty(() => toValue(dirty))
    window.addEventListener('beforeunload', beforeUnload)
  })
  onBeforeUnmount(() => {
    unregister()
    window.removeEventListener('beforeunload', beforeUnload)
  })
  onBeforeRouteLeave(() => !guarded() || askDiscard(DISCARD_QUESTION))
  return { confirmDiscard: async () => !toValue(dirty) || askDiscard(DISCARD_QUESTION) }
}

export async function confirmDiscard(dirty: boolean) {
  return !dirty || askDiscard(DISCARD_QUESTION)
}
