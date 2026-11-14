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
  Package,
  Settings2,
  Workflow,
} from 'lucide-vue-next'
import type { MeOverview } from '@dx/web-shared/types.ts'
import { appearance, term } from './appearance'

export interface NavLink {
  /** Stable key a sector pack uses to hide or reorder the module (see packs.py MENU_KEYS). */
  key: string
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
      { key: 'home', to: '/home', label: 'Việc hôm nay', icon: House, hint: 'Mọi việc đang chờ bạn' },
      {
        key: 'tasks',
        to: '/tasks',
        label: 'Công việc',
        icon: ListChecks,
        hint: 'Giao việc, nhận việc, theo dõi tiến độ',
        badge: (counts) => counts.tasks + counts.tasks_to_review,
      },
      {
        key: 'approvals',
        to: '/approvals',
        label: 'Cần phê duyệt',
        icon: ClipboardCheck,
        hint: 'Hồ sơ chờ bạn quyết định',
        badge: (counts) => counts.approvals,
      },
      { key: 'cases', to: '/cases', label: 'Hồ sơ', icon: Files, hint: 'Lập và theo dõi hồ sơ trình duyệt' },
      {
        key: 'chat',
        to: '/chat',
        label: 'Nhắn tin',
        icon: MessagesSquare,
        hint: 'Trò chuyện cá nhân và nhóm',
        badge: (counts) => counts.chat,
      },
      { key: 'feed', to: '/feed', label: 'Bảng tin', icon: Newspaper, hint: 'Thông báo và bài viết nội bộ' },
      { key: 'drive', to: '/drive', label: 'Kho tài liệu', icon: FolderClosed, hint: 'Tài liệu của bạn và được chia sẻ' },
      { key: 'reports', to: '/reports', label: 'Báo cáo', icon: BarChart3, hint: 'Số liệu công việc và hồ sơ' },
    ],
  },
  {
    label: 'Quản trị',
    links: [
      {
        key: 'processes',
        to: '/processes',
        label: 'Quy trình nghiệp vụ',
        icon: Workflow,
        hint: 'Quy trình hồ sơ và luồng tự động',
        capability: 'automations.manage',
      },
      {
        key: 'assistant',
        to: '/assistant',
        label: 'Trợ lý AI',
        icon: Bot,
        hint: 'Kiến thức và dịch vụ AI của trợ lý',
        capability: 'assistant.manage',
      },
      {
        key: 'packs',
        to: '/packs',
        label: 'Gói ngành',
        icon: Package,
        hint: 'Giao diện, từ ngữ và quy trình theo ngành',
        capability: 'organization.manage',
      },
      { key: 'settings', to: '/settings', label: 'Thiết lập', icon: Settings2, hint: 'Tổ chức, vai trò, nhật ký, giao diện' },
    ],
  },
]

export function visibleGroups(
  can: (capability: string) => boolean,
  menu = appearance.value?.menu,
  terms = appearance.value?.terminology,
): NavGroup[] {
  const hidden = new Set(menu?.hide ?? [])
  const order = menu?.order ?? []
  const rank = (key: string) => (order.includes(key) ? order.indexOf(key) : order.length + 1)
  return NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links
      .filter((link) => (!link.capability || can(link.capability)) && !hidden.has(link.key))
      // The pack's order first; modules it does not name keep their place after those.
      .map((link, index) => ({ link, index }))
      .sort((a, b) => rank(a.link.key) - rank(b.link.key) || a.index - b.index)
      .map(({ link }) => ({ ...link, label: term(link.label, terms), hint: term(link.hint, terms) })),
  })).filter((group) => group.links.length)
}

export function badgeText(count: number | undefined) {
  if (!count) return ''
  return count > 99 ? '99+' : String(count)
}
