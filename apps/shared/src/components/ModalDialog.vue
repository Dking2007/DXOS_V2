<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { X } from 'lucide-vue-next'
import { confirmDialog } from '../confirm'
const props = defineProps<{
  title: string
  wide?: boolean
  /** Unsaved edits inside: Esc, the backdrop and the close button ask before closing. */
  dirty?: boolean
  /** Custom check before closing; return false (or resolve to false) to keep the dialog open. */
  beforeClose?: () => boolean | Promise<boolean>
}>()
const emit = defineEmits<{ close: [] }>()
// Same wording as workspace-web's ui/unsaved.ts (DISCARD_QUESTION).
const DISCARD_QUESTION = 'Bạn có thay đổi chưa lưu. Rời đi và bỏ các thay đổi này?'
let closing = false
/** Every way out of the dialog goes through here; without `dirty`/`beforeClose` it closes at once. */
async function requestClose() {
  if (closing) return
  closing = true
  try {
    if (props.dirty && !(await confirmDialog({ message: DISCARD_QUESTION, confirmLabel: 'Bỏ thay đổi', danger: true }))) return
    if (props.beforeClose && !(await props.beforeClose())) return
    emit('close')
  } finally {
    closing = false
  }
}
const dialog = ref<HTMLDialogElement>()
// Unique per dialog, so a dialog opened from another one is still named correctly.
const titleId = `dialog-title-${useId()}`
let previous: Element | null = null
onMounted(async () => {
  previous = document.activeElement
  await nextTick()
  dialog.value?.showModal()
  // showModal() focuses the first focusable element, which is the close button; prefer the first field.
  dialog.value
    ?.querySelector<HTMLElement>('.modal-body :is(input, select, textarea):not([disabled], [type="hidden"])')
    ?.focus()
})
onBeforeUnmount(() => {
  if (previous instanceof HTMLElement) previous.focus()
})
</script>
<template>
  <dialog
    ref="dialog"
    class="modal"
    :class="{ wide }"
    :aria-labelledby="titleId"
    @cancel.prevent="requestClose"
    @click="
      (event) => {
        if (event.target === dialog) requestClose()
      }
    "
  >
    <header class="modal-header">
      <div>
        <h2 :id="titleId">{{ title }}</h2>
      </div>
      <button
        class="icon-button modal-close"
        type="button"
        aria-label="Đóng hộp thoại"
        title="Đóng (Esc)"
        @click="requestClose"
      >
        <X :size="20" aria-hidden="true" />
      </button>
    </header>
    <div class="modal-body"><slot /></div>
    <footer v-if="$slots.footer" class="modal-footer"><slot name="footer" /></footer>
  </dialog>
</template>
