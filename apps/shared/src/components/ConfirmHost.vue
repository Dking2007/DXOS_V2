<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { answerConfirm, pendingConfirm } from '../confirm'
import ModalDialog from './ModalDialog.vue'
</script>
<template>
  <!-- Esc, the backdrop and the close button all emit `close`, which answers "no". -->
  <ModalDialog
    v-if="pendingConfirm"
    :title="pendingConfirm.title ?? 'Xác nhận'"
    @close="answerConfirm(false)"
  >
    <p>{{ pendingConfirm.message }}</p>
    <template #footer>
      <!-- autofocus: the safe action gets the focus, so a stray Enter never destroys anything. -->
      <button
        class="button secondary"
        type="button"
        autofocus
        @click="answerConfirm(false)"
      >
        Hủy
      </button>
      <button
        class="button"
        :class="{ danger: pendingConfirm.danger }"
        type="button"
        @click="answerConfirm(true)"
      >
        {{ pendingConfirm.confirmLabel ?? 'Đồng ý' }}
      </button>
    </template>
  </ModalDialog>
</template>
