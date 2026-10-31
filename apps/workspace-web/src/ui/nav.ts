// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import type { Component } from 'vue'
import {
  BarChart3,
  Bot,
  ClipboardCheck,
  Files,
  FolderClosed,
  House,
  ListChecks,
  MessagesSquare,
  Newspaper,
  PackageOpen,
  Settings2,
  Workflow,
} from 'lucide-vue-next'
import type { MeOverview } from '@dx/web-shared/types.ts'

export interface NavLink {
  to: string
  label: string
  icon: Component
  hint: string
  capability?: string
  badge?: (counts: MeOverview['counts']) => number
}
export interface NavGroup {
  label: string
  links: NavLink[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Làm việc',
    links: [
      { to: '/home', label: 'Việc hôm nay', icon: House, hint: 'Mọi việc đang chờ bạn' },
      {
        to: '/tasks',
        label: 'Công việc',
        icon: ListChecks,
        hint: 'Giao việc, nhận việc, theo dõi tiến độ',
        badge: (counts) => counts.tasks + counts.tasks_to_review,
      },
      {
        to: '/approvals',
        label: 'Cần phê duyệt',
        icon: ClipboardCheck,
        hint: 'Hồ sơ chờ bạn quyết định',
        badge: (counts) => counts.approvals,
      },
      { to: '/cases', label: 'Hồ sơ', icon: Files, hint: 'Lập và theo dõi hồ sơ trình duyệt' },
    ],
  },
  {
    label: 'Trao đổi',
    links: [
      {
        to: '/chat',
        label: 'Nhắn tin',
        icon: MessagesSquare,
        hint: 'Trò chuyện cá nhân và nhóm',
        badge: (counts) => counts.chat,
      },
      { to: '/feed', label: 'Bảng tin', icon: Newspaper, hint: 'Thông báo và bài viết nội bộ' },
    ],
  },
  {
    label: 'Tài liệu & báo cáo',
    links: [
      { to: '/drive', label: 'Kho tài liệu', icon: FolderClosed, hint: 'Tài liệu của bạn và được chia sẻ' },
      { to: '/reports', label: 'Báo cáo', icon: BarChart3, hint: 'Số liệu công việc và hồ sơ' },
    ],
  },
  {
    label: 'Quản trị',
    links: [
      {
        to: '/automations',
        label: 'Tự động hóa',
        icon: Workflow,
        hint: 'Luồng tự động khi có sự kiện',
        capability: 'automations.manage',
      },
      {
        to: '/packages',
        label: 'Gói nghiệp vụ',
        icon: PackageOpen,
        hint: 'Quy trình duyệt cho từng loại hồ sơ',
        capability: 'forms.manage',
      },
      {
        to: '/assistant',
        label: 'Trợ lý AI',
        icon: Bot,
        hint: 'Kiến thức và dịch vụ AI của trợ lý',
        capability: 'assistant.manage',
      },
      { to: '/settings', label: 'Thiết lập', icon: Settings2, hint: 'Mẫu biểu, tổ chức, vai trò, giao diện' },
    ],
  },
]

export function visibleGroups(can: (capability: string) => boolean): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links.filter((link) => !link.capability || can(link.capability)),
  })).filter((group) => group.links.length)
}

export function badgeText(count: number | undefined) {
  if (!count) return ''
  return count > 99 ? '99+' : String(count)
}
