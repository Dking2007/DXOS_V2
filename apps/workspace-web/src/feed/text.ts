// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Formatting helpers for the feed: relative times, safe links and avatar colours.

import { formatDate, formatTime } from '../ui/preferences'

export const REACTIONS = [
  { kind: 'like', emoji: '👍', name: 'Thích' },
  { kind: 'love', emoji: '❤️', name: 'Yêu thích' },
  { kind: 'celebrate', emoji: '🎉', name: 'Chúc mừng' },
  { kind: 'insightful', emoji: '💡', name: 'Hữu ích' },
  { kind: 'support', emoji: '🤝', name: 'Ủng hộ' },
] as const

export function relativeTime(value: string, now = new Date()): string {
  const date = new Date(value)
  const seconds = Math.round((now.getTime() - date.getTime()) / 1000)
  if (Number.isNaN(seconds)) return value
  if (seconds < 60) return 'Vừa xong'
  if (seconds < 3600) return `${Math.floor(seconds / 60)} phút trước`
  const time = formatTime(date)
  const startOfToday = new Date(now)
  startOfToday.setHours(0, 0, 0, 0)
  if (date >= startOfToday) return `${Math.floor(seconds / 3600)} giờ trước`
  const startOfYesterday = new Date(startOfToday)
  startOfYesterday.setDate(startOfYesterday.getDate() - 1)
  if (date >= startOfYesterday) return `Hôm qua lúc ${time}`
  const sameYear = date.getFullYear() === now.getFullYear()
  return sameYear ? date.toLocaleDateString('vi-VN', { day: 'numeric', month: 'long' }) : formatDate(date)
}

export interface TextPart {
  text: string
  href?: string
}

const URL_PATTERN = /\bhttps?:\/\/[^\s<>"']+/g

/** Splits plain text into text and http(s) link parts; nothing else becomes markup. */
export function linkify(body: string): TextPart[] {
  const parts: TextPart[] = []
  let last = 0
  for (const match of body.matchAll(URL_PATTERN)) {
    // Trailing punctuation usually ends the sentence, not the address.
    const url = match[0].replace(/[.,;:!?)\]]+$/, '')
    const start = match.index ?? 0
    if (start > last) parts.push({ text: body.slice(last, start) })
    parts.push({ text: url, href: url })
    last = start + url.length
  }
  if (last < body.length) parts.push({ text: body.slice(last) })
  return parts
}

/** A stable hue per person, so the same colleague always gets the same avatar colour. */
export function avatarHue(name: string): number {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.codePointAt(0)!) >>> 0
  return hash % 360
}

export function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(-2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}

/** Long posts start collapsed so one announcement does not push everything else away. */
export function isLong(body: string) {
  return body.length > 480 || body.split('\n').length > 8
}

/** "Chào buổi sáng" … by the hour of the reader's clock. */
export function greeting(now = new Date()): string {
  const hour = now.getHours()
  if (hour < 11) return 'Chào buổi sáng'
  if (hour < 13) return 'Chào buổi trưa'
  if (hour < 18) return 'Chào buổi chiều'
  return 'Chào buổi tối'
}

/** "Thứ Ba, 24 tháng 11" for the feed's heading. */
export function longDay(now = new Date()): string {
  const days = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy']
  return `${days[now.getDay()]}, ${now.getDate()} tháng ${now.getMonth() + 1}`
}

/** Posts written since midnight of the reader's day. */
export function postedToday(dates: string[], now = new Date()): number {
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  return dates.filter((value) => new Date(value) >= start).length
}
