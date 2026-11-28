<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- One task as a sheet of paper on the board: tape in the colour of its priority, ruled lines, a folded
     corner, who holds it and when it is due, and an ink stamp once it is overdue or closed. -->
<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { AlarmClock, CalendarClock, ListChecks, Paperclip } from 'lucide-vue-next'
import { formatDate } from '@dx/web-shared/api.ts'
import type { Task } from '@dx/web-shared/types.ts'
import StatusBadge from '@dx/web-shared/components/StatusBadge.vue'
import { initials, stampOf, tilt } from '../ui/taskPaper'

const props = defineProps<{ task: Task }>()
const PRIORITY = { low: 'Thấp', normal: 'Bình thường', high: 'Cao', urgent: 'Khẩn' }
const holder = computed(() => props.task.assignee_name || props.task.department_name || '')
const stamp = computed(() => stampOf(props.task))
const progress = computed(() =>
  props.task.checklist_total
    ? Math.round((props.task.checklist_done / props.task.checklist_total) * 100)
    : 0,
)
</script>
<template>
  <RouterLink
    :to="`/tasks/${task.id}`"
    class="paper"
    :class="[`paper-${task.priority}`, { closed: ['completed', 'cancelled'].includes(task.status) }]"
    :style="{ '--tilt': `${tilt(task.id)}deg` }"
  >
    <span class="paper-sheet">
    <header class="paper-head">
      <StatusBadge kind="task" :status="task.status" />
      <span class="paper-priority">{{ PRIORITY[task.priority] }}</span>
    </header>
    <h3 class="paper-title" :title="task.title">{{ task.title }}</h3>
    <p v-if="task.description" class="paper-text">{{ task.description }}</p>
    <ul v-if="task.labels.length" class="paper-labels" aria-label="Nhãn">
      <li v-for="label in task.labels.slice(0, 3)" :key="label">#{{ label }}</li>
    </ul>
    <div v-if="task.checklist_total" class="paper-check">
      <span><ListChecks :size="14" />{{ task.checklist_done }}/{{ task.checklist_total }} mục</span>
      <span class="paper-bar" aria-hidden="true"><span :style="{ width: `${progress}%` }"></span></span>
    </div>
    <footer class="paper-foot">
      <span class="paper-holder" :title="holder || 'Chưa giao'">
        <span class="paper-avatar" aria-hidden="true">{{ initials(holder) }}</span>
        <span class="paper-name"
          >{{ holder || 'Chưa giao'
          }}<small v-if="!task.assignee_id && task.department_id"> · chờ phân công</small></span
        >
      </span>
      <span v-if="task.file_ids.length" class="paper-files" :title="`${task.file_ids.length} tệp đính kèm`"
        ><Paperclip :size="13" />{{ task.file_ids.length }}</span
      >
      <span v-if="task.due_at" class="paper-due" :class="{ late: task.overdue }">
        <component :is="task.overdue ? AlarmClock : CalendarClock" :size="13" />{{ formatDate(task.due_at) }}
      </span>
    </footer>
    <span v-if="stamp" class="paper-stamp" :class="`stamp-${stamp.tone}`" aria-hidden="true">{{
      stamp.label
    }}</span>
    </span>
    <span class="paper-tape" aria-hidden="true"></span>
  </RouterLink>
</template>
<style scoped>
/* The link leans and casts the shadow; the sheet inside has the folded corner cut out of it (a
   clip-path would also cut a box-shadow, so the shadow is a drop-shadow filter on the outside). */
.paper {
  --tape: var(--teal-line);
  --rule: color-mix(in srgb, var(--border) 55%, transparent);
  position: relative;
  display: flex;
  color: var(--text);
  text-decoration: none;
  filter: drop-shadow(0 1px 1px rgb(15 35 60 / 0.1)) drop-shadow(0 6px 8px rgb(15 35 60 / 0.12));
  transform: rotate(var(--tilt));
  transition:
    transform 0.18s ease,
    filter 0.18s ease;
}
.paper:hover,
.paper:focus-visible {
  filter: drop-shadow(0 2px 2px rgb(15 35 60 / 0.1)) drop-shadow(0 14px 16px rgb(15 35 60 / 0.2));
  transform: rotate(0deg) translateY(-4px);
}
.paper:focus-visible {
  outline: none;
}
.paper:focus-visible .paper-sheet {
  box-shadow: inset 0 0 0 2px var(--teal-ink);
}
.paper-sheet {
  position: relative;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  min-height: 210px;
  padding: 22px 18px 14px 28px;
  border-radius: 3px;
  background-color: var(--surface);
  /* Ruled lines and a margin line, like a sheet from a notebook. */
  background-image:
    linear-gradient(
      90deg,
      transparent 14px,
      color-mix(in srgb, var(--red-line) 85%, transparent) 14px 15px,
      transparent 15px
    ),
    repeating-linear-gradient(180deg, transparent 0 25px, var(--rule) 25px 26px);
  background-position:
    0 0,
    0 14px;
  clip-path: polygon(0 0, calc(100% - 22px) 0, 100% 22px, 100% 100%, 0 100%);
}
/* The folded-down corner. */
.paper-sheet::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 22px;
  height: 22px;
  border-bottom-left-radius: 3px;
  background: linear-gradient(225deg, transparent 50%, var(--surface-3) 50%);
}
.paper.closed {
  opacity: 0.78;
}
.paper.closed .paper-title {
  text-decoration: line-through;
  text-decoration-color: color-mix(in srgb, var(--muted) 60%, transparent);
}
/* A strip of tape holding the sheet, coloured by priority. */
.paper-tape {
  position: absolute;
  top: -7px;
  left: 50%;
  width: 74px;
  height: 16px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--tape) 75%, transparent);
  transform: translateX(-50%) rotate(-2deg);
  box-shadow: 0 1px 1px rgb(15 35 60 / 0.08);
}
.paper-low {
  --tape: var(--border-strong);
}
.paper-high {
  --tape: var(--amber-line, #f4d29b);
}
.paper-urgent {
  --tape: var(--red-line);
}
.paper-urgent .paper-priority {
  background: var(--red-soft);
  color: var(--red-ink);
}
.paper-high .paper-priority {
  background: var(--amber-soft);
  color: var(--amber-ink);
}
.paper-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.paper-priority {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--muted);
  font-size: 0.6875rem;
  font-weight: 600;
  white-space: nowrap;
}
.paper-title {
  display: -webkit-box;
  margin: 2px 0 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.paper-text {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  color: var(--muted);
  font-size: 0.8125rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
  white-space: pre-line;
}
.paper-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--violet-ink);
  font-size: 0.75rem;
  font-weight: 600;
}
.paper-check {
  display: grid;
  gap: 4px;
  color: var(--muted);
  font-size: 0.75rem;
}
.paper-check > span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.paper-bar {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--surface-3);
}
.paper-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--green-ink);
}
.paper-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed var(--border);
  color: var(--muted);
  font-size: 0.75rem;
}
.paper-holder {
  display: inline-flex;
  flex: 1;
  align-items: center;
  gap: 7px;
  min-width: 0;
}
.paper-avatar {
  display: grid;
  flex: none;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--teal-soft);
  color: var(--teal-ink);
  font-size: 0.625rem;
  font-weight: 700;
}
.paper-name {
  overflow: hidden;
  color: var(--text);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.paper-name small {
  color: var(--muted);
  font-weight: 400;
}
.paper-files,
.paper-due {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.paper-due.late {
  color: var(--red-ink);
  font-weight: 600;
}
/* Ink stamp, slightly crooked, over the lower right of the sheet. */
.paper-stamp {
  position: absolute;
  right: 14px;
  bottom: 52px;
  padding: 3px 10px;
  border: 2px solid currentColor;
  border-radius: 6px;
  background: color-mix(in srgb, var(--surface) 78%, transparent);
  font-size: 0.8125rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.72;
  transform: rotate(-12deg);
  pointer-events: none;
}
.stamp-red {
  color: var(--red-ink);
}
.stamp-green {
  color: var(--green-ink);
}
.stamp-grey {
  color: var(--muted);
}
.stamp-amber {
  color: var(--amber-ink);
}
/* Reduced motion (the system setting, or "Giảm chuyển động" in Cài đặt cá nhân): sheets lie straight. */
@media (prefers-reduced-motion: reduce) {
  :root:not([data-motion='full']) .paper,
  :root:not([data-motion='full']) .paper:hover {
    transform: none;
  }
}
:root[data-motion='reduce'] .paper,
:root[data-motion='reduce'] .paper:hover {
  transform: none;
  transition: none;
}
</style>
