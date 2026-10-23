<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useSession } from '../../stores/session'
import { markTourSeen, stepsFor, tourOpen, tourSeen } from '../../ui/tour'

const session = useSession()
const index = ref(0)
const rect = ref<DOMRect | null>(null)
const card = ref<HTMLElement>()
const steps = computed(() => stepsFor(session.user?.role))
const step = computed(() => steps.value[index.value])

function measure() {
  const target = step.value?.target
  const element = target ? document.querySelector<HTMLElement>(`[data-tour="${target}"]`) : null
  const box = element?.getBoundingClientRect()
  // Hidden targets (e.g. the sidebar on a phone) fall back to a centred card.
  rect.value = box && box.width > 0 && box.height > 0 ? box : null
}
const cardStyle = computed(() => {
  const box = rect.value
  if (!box) return {}
  const width = Math.min(340, window.innerWidth - 32)
  const left = Math.min(Math.max(16, box.left), window.innerWidth - width - 16)
  const below = box.bottom + 14
  if (below + 220 < window.innerHeight) return { top: `${below}px`, left: `${left}px`, width: `${width}px` }
  if (box.right + width + 30 < window.innerWidth)
    return { top: `${Math.max(16, box.top)}px`, left: `${box.right + 14}px`, width: `${width}px` }
  return { bottom: `${window.innerHeight - box.top + 14}px`, left: `${left}px`, width: `${width}px` }
})
const spotStyle = computed(() => {
  const box = rect.value
  if (!box) return { display: 'none' }
  return {
    top: `${box.top - 6}px`,
    left: `${box.left - 6}px`,
    width: `${box.width + 12}px`,
    height: `${box.height + 12}px`,
  }
})

async function go(to: number) {
  index.value = to
  await nextTick()
  measure()
  card.value?.focus()
}
function finish() {
  tourOpen.value = false
  if (session.user) markTourSeen(session.user.id)
}
function onKey(event: KeyboardEvent) {
  if (!tourOpen.value) return
  if (event.key === 'Escape') finish()
  else if (event.key === 'ArrowRight' && index.value < steps.value.length - 1) go(index.value + 1)
  else if (event.key === 'ArrowLeft' && index.value > 0) go(index.value - 1)
}
watch(tourOpen, (value) => {
  if (value) go(0)
})
watch(
  () => session.user?.id,
  (id) => {
    if (id && !tourSeen(id)) window.setTimeout(() => (tourOpen.value = true), 600)
  },
  { immediate: true },
)
onMounted(() => {
  window.addEventListener('resize', measure)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
  document.removeEventListener('keydown', onKey)
})
</script>
<template>
  <div v-if="tourOpen && step" class="tour-layer">
    <div class="tour-scrim" :class="{ dim: !rect }" @click="finish" />
    <div class="tour-spot" :style="spotStyle" aria-hidden="true" />
    <section
      ref="card"
      class="tour-card"
      :class="{ centered: !rect }"
      :style="cardStyle"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      tabindex="-1"
    >
      <span class="eyebrow">Hướng dẫn · {{ index + 1 }}/{{ steps.length }}</span>
      <h2 id="tour-title">{{ step.title }}</h2>
      <p>{{ step.body }}</p>
      <div class="tour-dots" aria-hidden="true">
        <i v-for="(_, dot) in steps" :key="dot" :class="{ on: dot === index }" />
      </div>
      <footer>
        <button class="link-button" type="button" @click="finish">Bỏ qua</button>
        <span class="grow" />
        <button v-if="index > 0" class="button secondary small" type="button" @click="go(index - 1)">Trước</button>
        <button
          v-if="index < steps.length - 1"
          class="button small"
          type="button"
          @click="go(index + 1)"
        >
          Tiếp
        </button>
        <button v-else class="button small" type="button" @click="finish">Bắt đầu làm việc</button>
      </footer>
    </section>
  </div>
</template>
