<script setup lang="ts">
import { CircleAlert, CircleCheck, Info, X } from 'lucide-vue-next'
import { dismiss, toasts } from '../../ui/toast'
</script>
<template>
  <div class="toaster" aria-live="polite" aria-relevant="additions">
    <TransitionGroup name="toast">
      <div
        v-for="item in toasts"
        :key="item.id"
        class="toast"
        :class="item.kind"
        :role="item.kind === 'error' ? 'alert' : 'status'"
      >
        <CircleCheck v-if="item.kind === 'success'" :size="18" />
        <CircleAlert v-else-if="item.kind === 'error'" :size="18" />
        <Info v-else :size="18" />
        <span>{{ item.text }}</span>
        <button
          v-if="item.action"
          class="toast-action"
          type="button"
          @click="
            () => {
              item.action?.run()
              dismiss(item.id)
            }
          "
        >
          {{ item.action.label }}
        </button>
        <button class="toast-close" type="button" aria-label="Đóng thông báo" @click="dismiss(item.id)">
          <X :size="15" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
