<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<script setup lang="ts">
import { Compass, Monitor, Moon, Sun } from 'lucide-vue-next'
import { applyTheme, theme, type ThemeChoice } from '../ui/theme'
import { startTour } from '../ui/tour'

const CHOICES: { key: ThemeChoice; label: string; hint: string; icon: typeof Sun }[] = [
  { key: 'light', label: 'Sáng', hint: 'Nền trắng, dễ đọc ban ngày', icon: Sun },
  { key: 'dark', label: 'Tối', hint: 'Dịu mắt khi làm việc buổi tối', icon: Moon },
  { key: 'system', label: 'Theo máy', hint: 'Đổi theo cài đặt của thiết bị', icon: Monitor },
]
</script>
<template>
  <section class="card">
    <header class="card-header">
      <div>
        <span class="eyebrow">GIAO DIỆN</span>
        <h2>Chế độ hiển thị</h2>
      </div>
    </header>
    <div class="card-body">
      <div class="theme-choices" role="radiogroup" aria-label="Chế độ hiển thị">
        <button
          v-for="choice in CHOICES"
          :key="choice.key"
          type="button"
          role="radio"
          class="theme-choice"
          :class="[choice.key, { active: theme === choice.key }]"
          :aria-checked="theme === choice.key"
          @click="applyTheme(choice.key)"
        >
          <span class="theme-preview" aria-hidden="true"><i /><i /><i /></span>
          <span class="theme-label"><component :is="choice.icon" :size="16" />{{ choice.label }}</span>
          <small>{{ choice.hint }}</small>
        </button>
      </div>
      <p class="muted" style="font-size: 13px; margin-top: 12px">
        Lựa chọn được nhớ trên trình duyệt này. Có thể đổi nhanh bằng nút mặt trời/mặt trăng ở thanh trên cùng.
      </p>
    </div>
  </section>
  <section class="card">
    <header class="card-header">
      <div>
        <span class="eyebrow">HƯỚNG DẪN</span>
        <h2>Làm quen với hệ thống</h2>
      </div>
    </header>
    <div class="card-body" style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap">
      <p class="muted" style="flex: 1; min-width: 240px">
        Xem lại các bước giới thiệu: menu, nút Tạo mới, tìm nhanh bằng Ctrl + K và thông báo.
      </p>
      <button class="button secondary" type="button" @click="startTour"><Compass :size="16" />Xem lại hướng dẫn</button>
    </div>
  </section>
</template>
