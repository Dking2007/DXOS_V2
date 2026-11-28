<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- A task's history as a workflow: opened, the card draws the steps on a canvas like the process
     designer; "Phóng to" shows the whole path left to right in a large, zoomable view. The card folds
     down to its latest step; the choice is remembered on this device. -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronDown, Maximize2 } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { activitySteps, toStep } from '../ui/taskActivity'
import type { ActivityEvent } from '../ui/taskActivity'
import TaskActivityCanvas from './TaskActivityCanvas.vue'
import { activityIcon } from './taskActivityIcons'

const props = defineProps<{ events: ActivityEvent[] }>()

const KEY = 'dx-task-activity-collapsed'
function load() {
  try {
    return window.localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}
const collapsed = ref(load())
function toggle() {
  collapsed.value = !collapsed.value
  try {
    window.localStorage.setItem(KEY, collapsed.value ? '1' : '0')
  } catch {
    /* private window: the card still folds, it just isn't remembered */
  }
}
const showAll = ref(false)
const enlarged = ref(false)
const view = computed(() => activitySteps(props.events, showAll.value ? undefined : 6))
const allSteps = computed(() => props.events.map(toStep))
const latest = computed(() => allSteps.value.at(-1) ?? null)
const uid = Math.random().toString(36).slice(2, 8)
const bodyId = `task-activity-${uid}`
</script>
<template>
  <section class="card activity" :class="{ 'is-collapsed': collapsed }">
    <header class="card-header activity-head">
      <button
        type="button"
        class="activity-toggle"
        :aria-expanded="!collapsed"
        :aria-controls="bodyId"
        @click="toggle"
      >
        <h3>Hoạt động</h3>
        <span class="activity-count">{{ events.length }}</span>
        <ChevronDown :size="18" class="activity-chevron" aria-hidden="true" />
        <span class="sr-only">{{ collapsed ? 'Mở rộng' : 'Thu gọn' }}</span>
      </button>
      <button
        v-if="events.length"
        type="button"
        class="icon-button activity-enlarge"
        aria-label="Phóng to sơ đồ hoạt động"
        title="Phóng to sơ đồ hoạt động"
        @click="enlarged = true"
      >
        <Maximize2 :size="16" />
      </button>
    </header>
    <button v-if="collapsed && latest" type="button" class="activity-latest" @click="toggle">
      <span class="activity-latest-icon" :class="`tone-${latest.tone}`" aria-hidden="true">
        <component :is="activityIcon(latest.action)" :size="14" />
      </span>
      <span class="activity-latest-text">
        <strong>{{ latest.label }}</strong>
        <small>{{ latest.actor || 'Hệ thống' }} · {{ formatDate(latest.at, true) }}</small>
      </span>
    </button>
    <div v-if="!collapsed" :id="bodyId" class="activity-body">
      <p v-if="!events.length" class="muted activity-empty">Chưa có hoạt động nào.</p>
      <template v-else>
        <button
          v-if="view.hidden"
          type="button"
          class="button ghost small activity-more"
          @click="showAll = true"
        >
          Hiện {{ view.hidden }} bước trước
        </button>
        <TaskActivityCanvas
          :key="view.steps.length"
          :flow-id="`activity-card-${uid}`"
          :steps="view.steps"
          :latest-id="latest?.id"
          direction="down"
        />
        <button
          v-if="showAll && events.length > 7"
          type="button"
          class="button ghost small activity-more"
          @click="showAll = false"
        >
          Chỉ hiện các bước gần đây
        </button>
        <!-- The canvas is a picture; the same history as text for screen readers. -->
        <ol class="sr-only">
          <li v-for="step in view.steps" :key="step.id">
            {{ step.label }}, {{ step.actor || 'Hệ thống' }}, {{ formatDate(step.at, true) }}.
            {{ step.note }} {{ step.reason }}
          </li>
        </ol>
      </template>
    </div>
    <ModalDialog
      v-if="enlarged"
      class="activity-modal"
      :title="`Hoạt động của công việc (${events.length})`"
      wide
      @close="enlarged = false"
    >
      <p class="muted activity-modal-hint">
        Các bước chính nối thành một đường; cập nhật phụ (sửa nội dung, đổi hạn, tệp) treo bên dưới
        bước trước đó. Kéo để di chuyển, cuộn để thu phóng.
      </p>
      <TaskActivityCanvas
        :flow-id="`activity-wide-${uid}`"
        :steps="allSteps"
        :latest-id="latest?.id"
        direction="right"
      />
    </ModalDialog>
  </section>
</template>
<style scoped>
.activity-head {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 var(--space-4) 0 0;
}
.activity-toggle {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: var(--space-5) var(--space-6);
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  border-radius: inherit;
}
.activity-toggle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}
.activity-toggle h3 {
  margin: 0;
}
.activity-count {
  min-width: 22px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--muted);
  font-size: 0.75rem;
  font-weight: 600;
  text-align: center;
}
.activity-chevron {
  margin-left: auto;
  color: var(--muted);
  transition: transform 0.18s;
}
.is-collapsed .activity-chevron {
  transform: rotate(-90deg);
}
.activity-latest {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 12px var(--space-6) 14px;
  border: 0;
  border-top: 1px solid var(--border);
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.activity-latest:hover {
  background: var(--surface-2);
}
.activity-latest-icon {
  display: grid;
  flex: none;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--tone-soft);
  color: var(--tone-ink);
}
.activity-latest-text {
  display: grid;
  min-width: 0;
}
.activity-latest-text strong {
  font-size: 0.875rem;
}
.activity-latest-text small {
  color: var(--muted);
  font-size: 0.75rem;
}
.activity-body {
  display: grid;
  overflow: hidden;
  border-top: 1px solid var(--border);
  border-radius: 0 0 8px 8px;
}
.activity-empty {
  margin: 0;
  padding: var(--space-5) var(--space-6);
}
.activity-more {
  justify-self: center;
  margin: 10px 0;
}
.modal.wide.activity-modal {
  width: min(1200px, calc(100vw - 32px));
}
.activity-modal-hint {
  margin: 0 0 12px;
  font-size: 0.8125rem;
}
.tone-start,
.tone-note {
  --tone-ink: var(--muted);
  --tone-soft: var(--surface-3);
}
.tone-progress {
  --tone-ink: var(--teal-ink);
  --tone-soft: var(--teal-soft);
}
.tone-done {
  --tone-ink: var(--green-ink);
  --tone-soft: var(--green-soft);
}
.tone-warn {
  --tone-ink: var(--amber-ink);
  --tone-soft: var(--amber-soft);
}
.tone-stop {
  --tone-ink: var(--red-ink);
  --tone-soft: var(--red-soft);
}
@media (prefers-reduced-motion: reduce) {
  .activity-chevron {
    transition: none;
  }
}
</style>
