// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// The look of the installed sector pack (gói ngành): name, logo, colours, font, login page,
// terminology, menu and home blocks. Loaded before the app mounts, from a public endpoint so the
// login page has it too. No pack in force means stock Desktiny, untouched.
import { computed, ref } from 'vue'

export type ColorSet = Record<string, string>
export interface AppearanceLook {
  app_name?: string
  org_name?: string
  logo?: string | null
  favicon?: string | null
  logo_url?: string | null
  favicon_url?: string | null
  colors?: { light?: ColorSet; dark?: ColorSet }
  font?: 'source-sans-3' | 'be-vietnam-pro' | null
  density?: 'comfortable' | 'compact'
  radius?: 'small' | 'medium' | 'large'
  login?: {
    style?: 'framed' | 'flat' | 'image'
    title?: string
    subtitle?: string
    background?: string | null
    background_url?: string | null
  }
  terminology?: Record<string, string>
  menu?: { hide?: string[]; order?: string[] }
  home?: string[] | null
}
export interface AppearanceState {
  pack_id: string | null
  revision: number
  appearance: AppearanceLook | null
}

export const appearance = ref<AppearanceLook | null>(null)
export const appearancePack = ref<string | null>(null)

export const brand = computed(() => ({
  name: appearance.value?.app_name || 'Desktiny',
  org: appearance.value?.org_name || '',
  logo: appearance.value?.logo_url || null,
}))

// ---- Colours and contrast (mirrors DEFAULT_COLORS / CONTRAST_PAIRS in packs.py) ----

export const DEFAULT_COLORS: { light: ColorSet; dark: ColorSet } = {
  light: {
    navy: '#0f172a',
    'ink-2': '#334155',
    muted: '#475569',
    canvas: '#f8fafc',
    surface: '#ffffff',
    'surface-2': '#f4f7fa',
    teal: '#1e3a5f',
    'teal-soft': '#e9eef5',
    'teal-ink': '#1e3a5f',
    red: '#b91c1c',
    'red-ink': '#b91c1c',
    'red-soft': '#fdecec',
    'green-ink': '#15803d',
    'green-soft': '#e8f6ee',
    'on-teal': '#ffffff',
  },
  dark: {
    navy: '#e3ecf4',
    'ink-2': '#bccbd9',
    muted: '#a9b8c8',
    canvas: '#0b1220',
    surface: '#111c2b',
    'surface-2': '#162333',
    teal: '#60a5fa',
    'teal-soft': '#172a44',
    'teal-ink': '#93c5fd',
    red: '#ff8798',
    'red-ink': '#ff95a4',
    'red-soft': '#3b1c24',
    'green-ink': '#74d6a8',
    'green-soft': '#13321f',
    'on-teal': '#0b1220',
  },
}
export const CONTRAST_PAIRS: [string, string, string][] = [
  ['navy', 'surface', 'Chữ chính trên nền thẻ'],
  ['navy', 'canvas', 'Chữ chính trên nền trang'],
  ['ink-2', 'surface', 'Chữ phụ đậm trên nền thẻ'],
  ['muted', 'surface', 'Chữ phụ trên nền thẻ'],
  ['teal-ink', 'surface', 'Liên kết, chữ nhấn'],
  ['teal-ink', 'teal-soft', 'Chữ trên nền nhấn nhạt'],
  ['on-teal', 'teal', 'Chữ trên nút chính'],
  ['red', 'surface', 'Chữ báo lỗi'],
  ['red-ink', 'red-soft', 'Nhãn lỗi'],
  ['green-ink', 'green-soft', 'Nhãn thành công'],
]

function luminance(color: string) {
  const channel = (value: number) => {
    const c = value / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16))
  return 0.2126 * channel(r!) + 0.7152 * channel(g!) + 0.0722 * channel(b!)
}
export function contrast(first: string, second: string) {
  const [a, b] = [luminance(first), luminance(second)].sort((x, y) => y - x)
  return (a! + 0.05) / (b! + 0.05)
}
/** Every checked pair in both themes; the server refuses the same pairs below 4.5:1. */
export function contrastReport(colors: AppearanceLook['colors']) {
  return (['light', 'dark'] as const).flatMap((theme) => {
    const palette = { ...DEFAULT_COLORS[theme], ...(colors?.[theme] ?? {}) }
    return CONTRAST_PAIRS.map(([text, background, label]) => {
      const ratio = contrast(palette[text]!, palette[background]!)
      return { theme, text, background, label, ratio: Math.round(ratio * 100) / 100, ok: ratio >= 4.5 }
    })
  })
}

/** The CSS a pack's colours turn into: light on :root, dark under both ways of choosing dark. */
export function colorCss(colors: AppearanceLook['colors'], scope = ':root') {
  const block = (set: ColorSet | undefined) =>
    Object.entries(set ?? {})
      .filter(([name, value]) => /^[a-z0-9-]+$/.test(name) && /^#[0-9a-fA-F]{6}$/.test(value))
      .map(([name, value]) => `--${name}: ${value};`)
      .join(' ')
  const light = block(colors?.light)
  const dark = block(colors?.dark)
  const parts: string[] = []
  if (light) parts.push(`${scope} { ${light} }`)
  if (dark) {
    const darkScope = scope === ':root' ? ":root[data-theme='dark']" : `[data-theme='dark'] ${scope}, ${scope}.dark`
    parts.push(`${darkScope} { ${dark} }`)
    if (scope === ':root')
      parts.push(`@media (prefers-color-scheme: dark) { :root:not([data-theme='light']) { ${dark} } }`)
  }
  return parts.join('\n')
}

// ---- Words ----

function lowerFirst(text: string) {
  return text.charAt(0).toLocaleLowerCase('vi') + text.slice(1)
}
/** The organisation's word for a stock one ("Hồ sơ" → "Hồ sơ học vụ"); capitalised or not. */
export function term(text: string, terms: Record<string, string> | undefined = appearance.value?.terminology) {
  if (!terms || !text) return text
  let result = text
  const pairs = Object.entries(terms).flatMap(([from, to]) => {
    const both: [string, string][] = [[from, to]]
    if (lowerFirst(from) !== from) both.push([lowerFirst(from), lowerFirst(to)])
    return both
  })
  // Longest first, so "Hồ sơ trình duyệt" wins over "Hồ sơ"; one pass, so a result is not replaced again.
  pairs.sort((a, b) => b[0].length - a[0].length)
  const pattern = new RegExp(pairs.map(([from]) => from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g')
  const map = new Map(pairs)
  result = result.replace(pattern, (match) => map.get(match) ?? match)
  return result
}

// ---- Applying ----

function setFavicon(url: string | null) {
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"][data-pack]')
  if (!url) {
    link?.remove()
    return
  }
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    link.dataset.pack = '1'
    document.head.appendChild(link)
  }
  link.href = url
}

export function applyAppearance(state: AppearanceState | null) {
  const look = state?.appearance ?? null
  appearance.value = look
  appearancePack.value = state?.pack_id ?? null
  const root = document.documentElement
  let style = document.getElementById('pack-appearance') as HTMLStyleElement | null
  if (!style) {
    style = document.createElement('style')
    style.id = 'pack-appearance'
    document.head.appendChild(style)
  }
  // Appended after every stylesheet, so the pack's values win over the stock ones.
  document.head.appendChild(style)
  style.textContent = look ? colorCss(look.colors) : ''
  for (const [key, value] of [
    ['font', look?.font && look.font !== 'source-sans-3' ? look.font : null],
    ['density', look?.density === 'compact' ? 'compact' : null],
    ['radius', look?.radius && look.radius !== 'medium' ? look.radius : null],
  ] as const) {
    if (value) root.dataset[key] = value
    else delete root.dataset[key]
  }
  setFavicon(look?.favicon_url ?? null)
  if (look?.app_name) document.title = look.app_name
}

/** Fetch and apply the look in force; a slow or failed answer leaves stock Desktiny. */
export async function loadAppearance(timeout = 1500) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch('/workspace/v1/appearance', {
      credentials: 'same-origin',
      signal: controller.signal,
    })
    if (response.ok) applyAppearance((await response.json()) as AppearanceState)
  } catch {
    // Offline, slow or blocked: the app still works in its stock look.
  } finally {
    clearTimeout(timer)
  }
}
