import { onBeforeUnmount, onMounted, type Ref } from 'vue'

// Closes a dropdown on a click outside it or on Escape, returning focus to its trigger.
export function useDismiss(root: Ref<HTMLElement | undefined>, open: Ref<boolean>, trigger?: Ref<HTMLElement | undefined>) {
  function onPointer(event: PointerEvent) {
    if (open.value && root.value && !root.value.contains(event.target as Node)) open.value = false
  }
  function onKey(event: KeyboardEvent) {
    if (open.value && event.key === 'Escape') {
      open.value = false
      trigger?.value?.focus()
    }
  }
  onMounted(() => {
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('pointerdown', onPointer)
    document.removeEventListener('keydown', onKey)
  })
}
