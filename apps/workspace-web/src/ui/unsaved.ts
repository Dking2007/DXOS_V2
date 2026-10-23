import { onBeforeUnmount, onMounted, toValue, type MaybeRefOrGetter } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

export const DISCARD_QUESTION = 'Bạn có thay đổi chưa lưu. Rời đi và bỏ các thay đổi này?'

// Asks before throwing away edits: on navigation, tab close/reload, and (via
// confirmDiscard) when a dialog holding a form is closed.
export function useUnsavedGuard(dirty: MaybeRefOrGetter<boolean>) {
  function beforeUnload(event: BeforeUnloadEvent) {
    if (!toValue(dirty)) return
    event.preventDefault()
    event.returnValue = ''
  }
  onMounted(() => window.addEventListener('beforeunload', beforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
  onBeforeRouteLeave(() => !toValue(dirty) || window.confirm(DISCARD_QUESTION))
  return { confirmDiscard: () => !toValue(dirty) || window.confirm(DISCARD_QUESTION) }
}

export function confirmDiscard(dirty: boolean) {
  return !dirty || window.confirm(DISCARD_QUESTION)
}
