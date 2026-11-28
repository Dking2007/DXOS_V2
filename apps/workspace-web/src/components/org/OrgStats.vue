<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The organisation in five numbers; the ones that need action open what is behind them. -->
<script setup lang="ts">
import { computed, type Component } from 'vue'
import { Building2, Crown, Layers, TriangleAlert, UserX, Users } from 'lucide-vue-next'
import type { OrgStats } from './orgTree'

const props = defineProps<{ stats: OrgStats; attentionOn: boolean }>()
const emit = defineEmits<{ unassigned: []; attention: [] }>()

interface Tile {
  key: string
  label: string
  value: number | string
  hint: string
  icon: Component
  tone: '' | 'warn' | 'danger' | 'ok'
  action?: () => void
  pressed?: boolean
}
const tiles = computed<Tile[]>(() => {
  const s = props.stats
  const list: Tile[] = [
    { key: 'departments', label: 'Phòng ban', value: s.departments, hint: s.empty ? `${s.empty} phòng không có người` : 'Mọi phòng đều có người', icon: Building2, tone: '' },
    { key: 'members', label: 'Thành viên', value: s.members, hint: 'Tài khoản đang hoạt động', icon: Users, tone: '' },
    {
      key: 'unassigned',
      label: 'Chưa xếp phòng',
      value: s.unassigned,
      hint: s.unassigned ? 'Bấm để xem và xếp phòng' : 'Ai cũng đã có phòng',
      icon: UserX,
      tone: s.unassigned ? 'warn' : 'ok',
      action: s.unassigned ? () => emit('unassigned') : undefined,
    },
    {
      key: 'leader',
      label: 'Phòng chưa có lãnh đạo',
      value: s.withoutLeader,
      hint: props.attentionOn ? 'Đang lọc phòng cần chú ý' : s.withoutLeader ? 'Bấm để lọc phòng cần chú ý' : 'Phòng nào cũng có lãnh đạo',
      icon: Crown,
      tone: s.withoutLeader ? 'warn' : 'ok',
      action: s.withoutLeader || props.attentionOn ? () => emit('attention') : undefined,
      pressed: props.attentionOn,
    },
    { key: 'depth', label: 'Độ sâu tối đa', value: s.maxDepth ? `${s.maxDepth} cấp` : '—', hint: 'Số tầng phòng ban lồng nhau', icon: Layers, tone: '' },
  ]
  if (s.broken)
    list.push({
      key: 'broken',
      label: 'Lỗi cơ cấu',
      value: s.broken,
      hint: 'Phòng cha bị vòng lặp hoặc đã mất',
      icon: TriangleAlert,
      tone: 'danger',
      action: () => emit('attention'),
      pressed: props.attentionOn,
    })
  return list
})
</script>
<template>
  <ul class="org-stats" aria-label="Tổng quan cơ cấu tổ chức">
    <li v-for="tile in tiles" :key="tile.key">
      <component
        :is="tile.action ? 'button' : 'div'"
        class="org-stat"
        :class="[tile.tone, { action: tile.action, pressed: tile.pressed }]"
        :type="tile.action ? 'button' : undefined"
        :aria-pressed="tile.action && tile.pressed !== undefined ? tile.pressed : undefined"
        @click="tile.action?.()"
      >
        <span class="org-stat-icon" aria-hidden="true"><component :is="tile.icon" :size="18" /></span>
        <span class="org-stat-text">
          <span class="org-stat-label">{{ tile.label }}</span>
          <strong>{{ tile.value }}</strong>
          <small>{{ tile.hint }}</small>
        </span>
      </component>
    </li>
  </ul>
</template>
<style scoped>
.org-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(176px, 1fr));
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.org-stats li {
  display: grid;
}
.org-stat {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--navy);
  text-align: left;
  font: inherit;
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.15s;
}
.org-stat.action {
  cursor: pointer;
}
.org-stat.action:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.org-stat.pressed {
  border-color: var(--amber);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--amber) 22%, transparent);
}
.org-stat-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--teal-soft);
  color: var(--teal-ink);
}
.org-stat.warn .org-stat-icon {
  background: var(--amber-soft);
  color: var(--amber-ink);
}
.org-stat.danger .org-stat-icon {
  background: var(--red-soft);
  color: var(--red-ink);
}
.org-stat.ok .org-stat-icon {
  background: var(--green-soft);
  color: var(--green-ink);
}
.org-stat-text {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.org-stat-label {
  color: var(--muted);
  font-size: 0.8125rem;
  font-weight: 600;
}
.org-stat strong {
  font-family: 'Be Vietnam Pro', sans-serif;
  font-size: 1.375rem;
  font-weight: 600;
  line-height: 1.3;
  font-variant-numeric: tabular-nums;
}
.org-stat small {
  color: var(--muted);
  font-size: 0.8125rem;
  line-height: 1.45;
}
@media (max-width: 640px) {
  .org-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .org-stat {
    padding: 12px;
    gap: 8px;
  }
  .org-stat-icon {
    width: 32px;
    height: 32px;
  }
  .org-stat small {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  :root:not([data-motion='full']) .org-stat.action:hover {
    transform: none;
  }
}
:root[data-motion='reduce'] .org-stat.action:hover {
  transform: none;
}
</style>
