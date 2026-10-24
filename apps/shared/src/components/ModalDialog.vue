<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLDialogElement>()
let previous: Element | null = null
onMounted(async () => {
  previous = document.activeElement
  await nextTick()
  dialog.value?.showModal()
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
    aria-labelledby="dialog-title"
    @cancel.prevent="emit('close')"
    @click="
      (event) => {
        if (event.target === dialog) emit('close')
      }
    "
  >
    <header class="modal-header">
      <div>
        <span class="eyebrow">Desktiny</span>
        <h2 id="dialog-title">{{ title }}</h2>
      </div>
      <button
        class="icon-button"
        aria-label="Đóng hộp thoại"
        @click="emit('close')"
      >
        <X :size="20" />
      </button>
    </header>
    <div class="modal-body"><slot /></div>
  </dialog>
</template>
