<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { aiActivity } from '../api'

/** Says the AI is still working once a request takes longer than a few seconds. */
const now = ref(Date.now())
let timer: number | undefined
watch(
  () => aiActivity.running > 0,
  (running) => {
    window.clearInterval(timer)
    if (running) timer = window.setInterval(() => (now.value = Date.now()), 1000)
  },
)
onBeforeUnmount(() => window.clearInterval(timer))
const seconds = computed(() => Math.floor((now.value - aiActivity.since) / 1000))
// A quick answer needs no notice; from 6 seconds on, people should know nothing is stuck.
const visible = computed(() => aiActivity.running > 0 && seconds.value >= 6)
</script>
<template>
  <Transition name="assistant-pop">
    <div v-if="visible" class="ai-busy" role="status" aria-live="polite">
      <Sparkles :size="16" class="ai-busy-icon" />
      <span
        ><strong>AI đang xử lý… {{ seconds }} giây</strong
        ><small v-if="seconds >= 15"
          >Dịch vụ AI chạy trên máy chủ của cơ quan có thể mất 1–2 phút. Cứ để trang mở, kết quả sẽ tự hiện.</small
        ></span
      >
    </div>
  </Transition>
</template>
<style scoped>
.ai-busy {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 80;
  transform: translateX(-50%);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: min(460px, calc(100vw - 32px));
  padding: 10px 16px;
  border: 1px solid var(--violet-line);
  border-radius: 14px;
  background: var(--violet-soft);
  color: var(--violet-ink);
  box-shadow: 0 10px 28px #0d2e4526;
  font-size: 13px;
}
.ai-busy strong,
.ai-busy small {
  display: block;
}
.ai-busy small {
  margin-top: 2px;
  color: var(--ink-2);
}
.ai-busy-icon {
  flex: none;
  margin-top: 1px;
  animation: ai-busy-pulse 1.4s ease-in-out infinite;
}
@keyframes ai-busy-pulse {
  50% {
    opacity: 0.35;
  }
}
@media (prefers-reduced-motion: reduce) {
  .ai-busy-icon {
    animation: none;
  }
}
@media (max-width: 900px) {
  .ai-busy {
    bottom: calc(80px + env(safe-area-inset-bottom));
  }
}
</style>
