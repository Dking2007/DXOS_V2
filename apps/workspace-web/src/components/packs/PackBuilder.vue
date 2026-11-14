<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The pack builder: the organisation's own pack (local.*), its look drawn with a live preview and
     the processes, flows and articles it carries chosen from what already exists. Saving never edits
     the system directly; the look applies only once someone chooses to use the pack. -->
<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { ArrowDown, ArrowUp, Check, ImagePlus, Moon, Plus, Save, Sun, Trash2, X } from 'lucide-vue-next'
import { api } from '../../api'
import { errorText } from '@dx/web-shared/api.ts'
import type { Page } from '@dx/web-shared/api.ts'
import { DEFAULT_COLORS, contrast, contrastReport, term } from '../../ui/appearance'
import type { AppearanceLook } from '../../ui/appearance'
import { NAV_GROUPS } from '../../ui/nav'
import { toast } from '../../ui/toast'

export interface PackLimits {
  colors: string[]
  fonts: Record<string, string>
  login_styles: Record<string, string>
  menu: string[]
  hideable: string[]
  home: Record<string, string>
}
export interface LocalPack {
  pack_id: string
  name: string
  version: string
  description: string
  appearance: AppearanceLook | null
  includes: { processes?: string[]; automations?: string[]; knowledge?: string[] }
  revision: number
}
const props = defineProps<{ pack: LocalPack | null; limits: PackLimits }>()
const emit = defineEmits<{ saved: [packId: string]; close: [] }>()

const MAIN_COLORS: [string, string][] = [
  ['teal', 'Màu chính (nút, thanh chọn)'],
  ['teal-strong', 'Màu chính đậm'],
  ['teal-soft', 'Nền nhấn nhạt'],
  ['teal-ink', 'Chữ nhấn, liên kết'],
  ['navy', 'Chữ chính'],
  ['muted', 'Chữ phụ'],
  ['canvas', 'Nền trang'],
  ['surface', 'Nền thẻ'],
]
const SUGGESTED_TERMS = ['Hồ sơ', 'Phòng ban', 'Công việc', 'Quy trình nghiệp vụ', 'Kho tài liệu', 'Bảng tin']
// Colours of the preview that the contrast check does not cover.
const PREVIEW_EXTRA = {
  light: { border: '#dbe2ea', 'teal-strong': '#16304f', 'surface-3': '#e9eef5' },
  dark: { border: '#2a3b4c', 'teal-strong': '#93c5fd', 'surface-3': '#1d2c3e' },
}

const look = props.pack?.appearance ?? {}
const isNew = !props.pack
const packId = ref(props.pack?.pack_id ?? 'local.co-quan')
const name = ref(props.pack?.name ?? 'Giao diện của cơ quan')
const version = ref(props.pack?.version ?? '1.0.0')
const description = ref(props.pack?.description ?? '')
const withLook = ref(isNew || !!props.pack?.appearance)
const form = reactive({
  app_name: look.app_name ?? '',
  org_name: look.org_name ?? '',
  logo: look.logo ?? null,
  favicon: look.favicon ?? null,
  font: look.font ?? 'source-sans-3',
  density: look.density ?? 'comfortable',
  radius: look.radius ?? 'medium',
  login: {
    style: look.login?.style ?? 'framed',
    title: look.login?.title ?? '',
    subtitle: look.login?.subtitle ?? '',
    background: look.login?.background ?? null,
    ground: look.login?.ground ?? null,
    ground_to: look.login?.ground_to ?? null,
    button_label: look.login?.button_label ?? '',
    note: look.login?.note ?? '',
    effects: look.login?.effects !== false,
  },
})
// The login page writes light lettering (#e8eef8) on its ground: a ground must keep it readable.
const LOGIN_INK = '#e8eef8'
const STOCK_GROUND = { from: '#183670', to: '#081634' }
const loginGroundIssue = computed(() =>
  [form.login.ground, form.login.ground_to].some((value) => value && contrast(LOGIN_INK, value) < 4.5)
    ? 'Màu nền trang đăng nhập quá sáng: chữ trắng khó đọc (cần tương phản ≥ 4,5:1).'
    : '',
)
const loginPreview = computed(() => {
  const from = form.login.ground || null
  const to = form.login.ground_to || from
  if (!withLook.value || !from || !to) return undefined
  return { background: `linear-gradient(160deg, ${from}, ${to})` }
})
const colors = reactive({ light: { ...(look.colors?.light ?? {}) }, dark: { ...(look.colors?.dark ?? {}) } })
const terms = ref<{ from: string; to: string }[]>(
  Object.entries(look.terminology ?? {}).map(([from, to]) => ({ from, to })),
)
const allLinks = NAV_GROUPS.flatMap((group) => group.links)
const menuOrder = ref<string[]>(
  [...(look.menu?.order ?? []), ...props.limits.menu.filter((key) => !(look.menu?.order ?? []).includes(key))],
)
const hidden = ref<string[]>([...(look.menu?.hide ?? [])])
const homeBlocks = ref<string[]>(look.home ?? Object.keys(props.limits.home).filter((key) => key !== 'ai.digest'))
const assetUrls = reactive<Record<string, string | null>>({
  logo: look.logo_url ?? null,
  favicon: look.favicon_url ?? null,
  background: look.login?.background_url ?? null,
})
const include = reactive({
  processes: [...(props.pack?.includes.processes ?? [])],
  automations: [...(props.pack?.includes.automations ?? [])],
  knowledge: [...(props.pack?.includes.knowledge ?? [])],
})
const tab = ref<'look' | 'business'>('look')
const previewTheme = ref<'light' | 'dark'>('light')
const busy = ref(false)
const error = ref<unknown>(null)
const extraColor = ref('')

const rules = useQuery({
  queryKey: ['automations'],
  queryFn: () =>
    api.request<Page<{ id: string; name: string; kind: string; description: string }>>('/automations'),
})
const articles = useQuery({
  queryKey: ['assistant-articles'],
  queryFn: () => api.request<Page<{ id: string; title: string; source?: string }>>('/assistant/articles'),
})

const appearance = computed<AppearanceLook>(() => ({
  app_name: form.app_name.trim(),
  org_name: form.org_name.trim(),
  logo: form.logo,
  favicon: form.favicon,
  colors: { light: { ...colors.light }, dark: { ...colors.dark } },
  font: form.font as AppearanceLook['font'],
  density: form.density as AppearanceLook['density'],
  radius: form.radius as AppearanceLook['radius'],
  login: { ...form.login, style: form.login.style as 'framed' | 'flat' | 'image' },
  terminology: Object.fromEntries(
    terms.value.filter((item) => item.from.trim() && item.to.trim()).map((item) => [item.from.trim(), item.to.trim()]),
  ),
  menu: {
    hide: hidden.value,
    order: menuOrder.value.filter((key) => props.limits.menu.includes(key)),
  },
  home: homeBlocks.value,
}))
const report = computed(() => contrastReport(appearance.value.colors))
const failing = computed(() => report.value.filter((item) => !item.ok))

function setColor(theme: 'light' | 'dark', key: string, value: string) {
  if (/^#[0-9a-fA-F]{6}$/.test(value)) colors[theme][key] = value.toLowerCase()
}
function resetColor(theme: 'light' | 'dark', key: string) {
  delete colors[theme][key]
}
function colorOf(theme: 'light' | 'dark', key: string) {
  return colors[theme][key] ?? DEFAULT_COLORS[theme][key] ?? PREVIEW_EXTRA[theme][key as 'border'] ?? '#888888'
}
const editedKeys = computed(() =>
  [...new Set([...MAIN_COLORS.map(([key]) => key), ...Object.keys(colors.light), ...Object.keys(colors.dark)])],
)
function addColor() {
  if (extraColor.value && !editedKeys.value.includes(extraColor.value))
    colors.light[extraColor.value] = colorOf('light', extraColor.value)
  extraColor.value = ''
}
function labelOf(key: string) {
  return MAIN_COLORS.find(([item]) => item === key)?.[1] ?? `--${key}`
}

function move(list: string[], index: number, step: number) {
  const target = index + step
  if (target < 0 || target >= list.length) return
  ;[list[index], list[target]] = [list[target]!, list[index]!]
}
function toggle(list: string[], key: string) {
  const index = list.indexOf(key)
  if (index >= 0) list.splice(index, 1)
  else list.push(key)
}
function linkLabel(key: string) {
  const link = allLinks.find((item) => item.key === key)
  return link ? term(link.label, appearance.value.terminology) : key
}

async function upload(role: 'logo' | 'favicon' | 'background', event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const body = new FormData()
  body.append('role', role)
  body.append('file', file)
  try {
    const result = await api.request<{ path: string; url: string; cleaned: boolean }>(
      `/packs/${encodeURIComponent(packId.value)}/assets`,
      { method: 'POST', body },
    )
    if (role === 'background') form.login.background = result.path
    else form[role] = result.path
    assetUrls[role] = result.url
    if (result.cleaned) toast.success('Đã bỏ phần có thể chạy mã khỏi tệp SVG.')
  } catch (cause) {
    toast.error(cause)
  }
}
function clearAsset(role: 'logo' | 'favicon' | 'background') {
  if (role === 'background') form.login.background = null
  else form[role] = null
  assetUrls[role] = null
}

async function save() {
  error.value = null
  if (withLook.value && failing.value.length) {
    error.value = new Error('Còn cặp màu khó đọc; chỉnh lại trước khi lưu.')
    return
  }
  if (withLook.value && loginGroundIssue.value) {
    error.value = new Error(loginGroundIssue.value)
    return
  }
  busy.value = true
  try {
    await api.request(`/packs/${encodeURIComponent(packId.value)}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: name.value,
        version: version.value,
        description: description.value,
        appearance: withLook.value ? appearance.value : null,
        include,
        expected_revision: props.pack?.revision ?? null,
      }),
    })
    toast.success('Đã lưu gói của cơ quan.')
    emit('saved', packId.value)
  } catch (cause) {
    error.value = cause
  } finally {
    busy.value = false
  }
}

/** Variables for the preview box only; the rest of the app keeps its current look. */
const previewVars = computed(() => {
  const theme = previewTheme.value
  const palette: Record<string, string> = {
    ...PREVIEW_EXTRA[theme],
    ...DEFAULT_COLORS[theme],
    ...(withLook.value ? colors[theme] : {}),
  }
  return Object.fromEntries(Object.entries(palette).map(([key, value]) => [`--${key}`, value]))
})
const previewName = computed(() => (withLook.value && form.app_name.trim()) || 'Desktiny')
const previewLinks = computed(() =>
  menuOrder.value
    .filter((key) => !hidden.value.includes(key) && allLinks.some((link) => link.key === key))
    .slice(0, 8)
    .map((key) => ({ key, label: linkLabel(key), icon: allLinks.find((link) => link.key === key)!.icon })),
)
</script>
<template>
  <section class="card pack-builder">
    <header class="card-header">
      <div>
        <h2>{{ isNew ? 'Tạo gói của cơ quan' : `Sửa “${pack?.name}”` }}</h2>
        <small class="muted">Lưu thành một gói riêng; chọn “Dùng giao diện này” ở danh sách gói để áp dụng.</small>
      </div>
      <div class="inline-actions">
        <button class="button secondary small" type="button" @click="emit('close')"><X :size="15" />Đóng</button>
        <button class="button small" type="button" :disabled="busy" @click="save">
          <Save :size="15" />{{ busy ? 'Đang lưu…' : 'Lưu gói' }}
        </button>
      </div>
    </header>
    <div v-if="error" class="notice error" style="margin: 0 18px 12px">{{ errorText(error) }}</div>
    <div class="card-body pack-meta form-grid">
      <div class="field">
        <label for="pack-id">Mã gói</label
        ><input id="pack-id" v-model="packId" :disabled="!isNew" pattern="local\.[a-z0-9][a-z0-9-]*" required />
        <small>Dạng local.ten-goi, chữ thường không dấu.</small>
      </div>
      <div class="field">
        <label for="pack-name">Tên gói</label><input id="pack-name" v-model="name" maxlength="120" required />
      </div>
      <div class="field">
        <label for="pack-version">Phiên bản</label><input id="pack-version" v-model="version" pattern="\d+\.\d+\.\d+" />
      </div>
      <div class="field">
        <label for="pack-desc">Mô tả</label><input id="pack-desc" v-model="description" maxlength="1000" />
      </div>
    </div>
    <div class="tabs pack-tabs" role="tablist">
      <button class="tab" :class="{ active: tab === 'look' }" role="tab" @click="tab = 'look'">Giao diện</button>
      <button class="tab" :class="{ active: tab === 'business' }" role="tab" @click="tab = 'business'">
        Nghiệp vụ<span
          v-if="include.processes.length + include.automations.length + include.knowledge.length"
          class="tab-count"
          >{{ include.processes.length + include.automations.length + include.knowledge.length }}</span
        >
      </button>
    </div>

    <div v-if="tab === 'look'" class="pack-look">
      <div class="pack-form">
        <label class="checkbox-label"
          ><input v-model="withLook" type="checkbox" /> Gói này có phần giao diện</label
        >
        <template v-if="withLook">
          <fieldset>
            <legend>Tên và logo</legend>
            <div class="form-grid">
              <div class="field">
                <label for="look-app">Tên ứng dụng</label
                ><input id="look-app" v-model="form.app_name" maxlength="60" placeholder="Desktiny" />
              </div>
              <div class="field">
                <label for="look-org">Tên cơ quan</label
                ><input id="look-org" v-model="form.org_name" maxlength="120" placeholder="Không bắt buộc" />
              </div>
            </div>
            <div class="pack-assets">
              <div v-for="role in ['logo', 'favicon'] as const" :key="role" class="pack-asset">
                <span class="pack-asset-box"
                  ><img v-if="assetUrls[role]" :src="assetUrls[role]!" alt="" /><ImagePlus v-else :size="20"
                /></span>
                <div>
                  <strong>{{ role === 'logo' ? 'Logo' : 'Biểu tượng tab (favicon)' }}</strong>
                  <small>PNG, WebP hoặc SVG; SVG được lọc bỏ mã.</small>
                  <div class="inline-actions">
                    <label class="button secondary small"
                      >Chọn tệp<input
                        type="file"
                        accept="image/png,image/webp,image/svg+xml"
                        class="sr-only"
                        @change="upload(role, $event)"
                    /></label>
                    <button v-if="form[role]" class="button ghost small" type="button" @click="clearAsset(role)">
                      Bỏ
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Màu sắc</legend>
            <div class="pack-colors">
              <span />
              <small class="muted"><Sun :size="13" /> Sáng</small>
              <small class="muted"><Moon :size="13" /> Tối</small>
              <template v-for="key in editedKeys" :key="key">
                <span class="pack-color-label">{{ labelOf(key) }}</span>
                <span v-for="theme in ['light', 'dark'] as const" :key="theme" class="pack-color">
                  <input
                    type="color"
                    :value="colorOf(theme, key)"
                    :aria-label="`${labelOf(key)} (${theme === 'light' ? 'sáng' : 'tối'})`"
                    @input="setColor(theme, key, ($event.target as HTMLInputElement).value)"
                  /><code :class="{ muted: !colors[theme][key] }">{{ colorOf(theme, key) }}</code
                  ><button
                    v-if="colors[theme][key]"
                    class="icon-button"
                    type="button"
                    aria-label="Về màu mặc định"
                    title="Về màu mặc định"
                    @click="resetColor(theme, key)"
                  >
                    <X :size="13" />
                  </button>
                </span>
              </template>
            </div>
            <div class="inline-actions" style="margin-top: 8px">
              <select v-model="extraColor" class="compact-select" aria-label="Thêm màu khác">
                <option value="">Thêm màu khác…</option>
                <option v-for="key in limits.colors.filter((k) => !editedKeys.includes(k))" :key="key" :value="key">
                  --{{ key }}
                </option>
              </select>
              <button class="button ghost small" type="button" :disabled="!extraColor" @click="addColor">
                <Plus :size="14" />Thêm
              </button>
            </div>
            <div class="pack-contrast" :class="{ bad: failing.length }">
              <strong v-if="!failing.length"><Check :size="15" /> Mọi cặp màu đều dễ đọc (tương phản ≥ 4,5:1).</strong>
              <template v-else>
                <strong>Cặp màu khó đọc, cần chỉnh trước khi lưu:</strong>
                <span v-for="item in failing" :key="item.theme + item.label"
                  >{{ item.label }} ({{ item.theme === 'light' ? 'sáng' : 'tối' }}): {{ item.ratio }}:1</span
                >
              </template>
            </div>
          </fieldset>

          <fieldset>
            <legend>Chữ và bố cục</legend>
            <div class="form-grid">
              <div class="field">
                <label for="look-font">Phông chữ</label
                ><select id="look-font" v-model="form.font">
                  <option v-for="(label, key) in limits.fonts" :key="key" :value="key">{{ label }}</option>
                </select>
              </div>
              <div class="field">
                <label for="look-density">Mật độ</label
                ><select id="look-density" v-model="form.density">
                  <option value="comfortable">Thoáng (mặc định)</option>
                  <option value="compact">Gọn</option>
                </select>
              </div>
              <div class="field">
                <label for="look-radius">Bo góc</label
                ><select id="look-radius" v-model="form.radius">
                  <option value="small">Ít</option>
                  <option value="medium">Vừa (mặc định)</option>
                  <option value="large">Nhiều</option>
                </select>
              </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Trang đăng nhập</legend>
            <div class="form-grid">
              <div class="field">
                <label for="login-style">Kiểu</label
                ><select id="login-style" v-model="form.login.style">
                  <option v-for="(label, key) in limits.login_styles" :key="key" :value="key">{{ label }}</option>
                </select>
              </div>
              <div class="field">
                <label for="login-title">Tiêu đề</label
                ><input id="login-title" v-model="form.login.title" maxlength="120" placeholder="Hệ thống văn phòng điện tử" />
              </div>
              <div class="field">
                <label for="login-sub">Dòng phụ</label
                ><input id="login-sub" v-model="form.login.subtitle" maxlength="160" placeholder="E-OFFICE · KHÔNG GIAN NỘI BỘ" />
              </div>
            </div>
            <div class="form-grid">
              <div class="field">
                <label for="login-button">Chữ trên nút</label
                ><input id="login-button" v-model="form.login.button_label" maxlength="40" placeholder="Đăng nhập bằng SSO" />
              </div>
              <div class="field">
                <label for="login-note">Dòng ghi chú dưới nút</label
                ><input
                  id="login-note"
                  v-model="form.login.note"
                  maxlength="200"
                  placeholder="Đăng nhập bằng tài khoản của tổ chức…"
                />
              </div>
            </div>
            <div class="pack-login-ground">
              <span class="section-label">Màu nền{{ form.login.style === 'image' ? ' (phủ lên ảnh)' : '' }}</span>
              <span v-for="key in ['ground', 'ground_to'] as const" :key="key" class="pack-color">
                <input
                  type="color"
                  :value="form.login[key] || (key === 'ground' ? STOCK_GROUND.from : STOCK_GROUND.to)"
                  :aria-label="key === 'ground' ? 'Màu nền trên' : 'Màu nền dưới'"
                  @input="form.login[key] = ($event.target as HTMLInputElement).value"
                /><code :class="{ muted: !form.login[key] }">{{
                  form.login[key] || (key === 'ground' ? 'mặc định' : 'như màu trên')
                }}</code
                ><button
                  v-if="form.login[key]"
                  class="icon-button"
                  type="button"
                  aria-label="Về màu mặc định"
                  title="Về màu mặc định"
                  @click="form.login[key] = null"
                >
                  <X :size="13" />
                </button>
              </span>
              <small v-if="loginGroundIssue" class="overdue-text">{{ loginGroundIssue }}</small>
            </div>
            <label v-if="form.login.style === 'framed'" class="checkbox-label"
              ><input v-model="form.login.effects" type="checkbox" /> Hiệu ứng chuyển động (ánh sáng, hạt sáng, khung vẽ
              dần)</label
            >
            <div v-if="form.login.style === 'image'" class="pack-asset">
              <span class="pack-asset-box wide"
                ><img v-if="assetUrls.background" :src="assetUrls.background" alt="" /><ImagePlus v-else :size="20"
              /></span>
              <div>
                <strong>Ảnh nền</strong><small>PNG, JPEG hoặc WebP, tối đa 2 MB.</small>
                <label class="button secondary small"
                  >Chọn ảnh<input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    class="sr-only"
                    @change="upload('background', $event)"
                /></label>
              </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Từ ngữ</legend>
            <small class="muted">Đổi chữ hiển thị ở menu, tiêu đề trang và trang chủ; không đổi dữ liệu hay đường dẫn.</small>
            <div v-for="(item, index) in terms" :key="index" class="pack-term">
              <input v-model="item.from" maxlength="60" placeholder="Chữ gốc" aria-label="Chữ gốc" /><span>→</span
              ><input v-model="item.to" maxlength="80" placeholder="Chữ thay" aria-label="Chữ thay" /><button
                class="icon-button"
                type="button"
                aria-label="Bỏ cặp từ"
                @click="terms.splice(index, 1)"
              >
                <Trash2 :size="15" />
              </button>
            </div>
            <div class="chip-row">
              <button
                v-for="word in SUGGESTED_TERMS.filter((w) => !terms.some((t) => t.from === w))"
                :key="word"
                type="button"
                class="chip"
                @click="terms.push({ from: word, to: '' })"
              >
                + {{ word }}
              </button>
              <button type="button" class="chip" @click="terms.push({ from: '', to: '' })">+ Khác</button>
            </div>
          </fieldset>

          <fieldset>
            <legend>Menu</legend>
            <ul class="pack-order">
              <li v-for="(key, index) in menuOrder" :key="key" :class="{ off: hidden.includes(key) }">
                <label class="checkbox-label"
                  ><input
                    type="checkbox"
                    :checked="!hidden.includes(key)"
                    :disabled="!limits.hideable.includes(key)"
                    @change="toggle(hidden, key)"
                  />{{ linkLabel(key) }}</label
                >
                <button class="icon-button" type="button" aria-label="Lên" @click="move(menuOrder, index, -1)">
                  <ArrowUp :size="14" /></button
                ><button class="icon-button" type="button" aria-label="Xuống" @click="move(menuOrder, index, 1)">
                  <ArrowDown :size="14" />
                </button>
              </li>
            </ul>
            <small class="muted">Chỉ ẩn được phân hệ làm việc; trang chủ, phê duyệt và quản trị luôn hiện.</small>
          </fieldset>

          <fieldset>
            <legend>Trang chủ</legend>
            <ul class="pack-order">
              <li v-for="(label, key) in limits.home" :key="key" :class="{ off: !homeBlocks.includes(key) }">
                <label class="checkbox-label"
                  ><input type="checkbox" :checked="homeBlocks.includes(key)" @change="toggle(homeBlocks, key)" />{{
                    label
                  }}</label
                >
                <template v-if="homeBlocks.includes(key)">
                  <button
                    class="icon-button"
                    type="button"
                    aria-label="Lên"
                    @click="move(homeBlocks, homeBlocks.indexOf(key), -1)"
                  >
                    <ArrowUp :size="14" /></button
                  ><button
                    class="icon-button"
                    type="button"
                    aria-label="Xuống"
                    @click="move(homeBlocks, homeBlocks.indexOf(key), 1)"
                  >
                    <ArrowDown :size="14" />
                  </button>
                </template>
              </li>
            </ul>
          </fieldset>
        </template>
      </div>

      <aside class="pack-preview" :style="previewVars" aria-label="Xem trước giao diện">
        <div class="pack-preview-head">
          <strong>Xem trước</strong>
          <div class="segmented">
            <button type="button" :class="{ active: previewTheme === 'light' }" @click="previewTheme = 'light'">
              <Sun :size="14" />Sáng</button
            ><button type="button" :class="{ active: previewTheme === 'dark' }" @click="previewTheme = 'dark'">
              <Moon :size="14" />Tối
            </button>
          </div>
        </div>
        <div class="pv-app" :class="[`pv-font-${form.font}`, `pv-radius-${form.radius}`]">
          <div class="pv-side">
            <div class="pv-brand">
              <span class="pv-mark"
                ><img v-if="withLook && assetUrls.logo" :src="assetUrls.logo" alt="" /><template v-else>{{
                  previewName.charAt(0)
                }}</template></span
              ><span
                ><b>{{ previewName }}</b><small v-if="withLook && form.org_name">{{ form.org_name }}</small></span
              >
            </div>
            <span
              v-for="(link, index) in previewLinks"
              :key="link.key"
              class="pv-link"
              :class="{ active: index === 0 }"
              ><component :is="link.icon" :size="14" />{{ link.label }}</span
            >
          </div>
          <div class="pv-main">
            <div class="pv-card">
              <b>{{ term('Hồ sơ', appearance.terminology) }} chờ duyệt</b>
              <small>Chữ phụ: cập nhật 5 phút trước</small>
              <p>Chữ chính trên nền thẻ. <a>Liên kết</a></p>
              <div class="pv-row">
                <span class="pv-button">Nút chính</span><span class="pv-chip">Nền nhấn nhạt</span
                ><span class="pv-ok">Đã duyệt</span><span class="pv-bad">Bị trả lại</span>
              </div>
            </div>
          </div>
        </div>
        <div class="pv-login" :class="`pv-login-${form.login.style}`" :style="loginPreview">
          <span class="pv-mark round"
            ><img v-if="withLook && assetUrls.logo" :src="assetUrls.logo" alt="" /><template v-else>{{
              previewName.charAt(0)
            }}</template></span
          >
          <small>{{ previewName.toLocaleUpperCase('vi') }}</small>
          <b>{{ (withLook && form.login.title) || 'Hệ thống văn phòng điện tử' }}</b>
          <small>{{ (withLook && form.login.subtitle) || 'E-OFFICE · KHÔNG GIAN NỘI BỘ' }}</small>
          <span class="pv-login-button">{{ (withLook && form.login.button_label) || 'Đăng nhập bằng SSO' }}</span>
          <small v-if="withLook && form.login.note" class="pv-login-note">{{ form.login.note }}</small>
        </div>
      </aside>
    </div>

    <div v-else class="card-body pack-business">
      <p class="muted">
        Chọn những gì đã có để đưa vào gói. Khi xuất, chúng được ghi thành tệp; cơ quan khác cài gói sẽ có bản riêng.
        Gói của cơ quan chỉ trỏ tới các mục này, gỡ gói không xoá chúng.
      </p>
      <div class="pack-pick">
        <section>
          <span class="section-label">Quy trình hồ sơ</span>
          <label
            v-for="rule in (rules.data.value?.items ?? []).filter((r) => r.kind === 'process')"
            :key="rule.id"
            class="checkbox-label"
            ><input
              type="checkbox"
              :checked="include.processes.includes(rule.id)"
              @change="toggle(include.processes, rule.id)"
            />{{ rule.name }}</label
          >
        </section>
        <section>
          <span class="section-label">Luồng tự động</span>
          <label
            v-for="rule in (rules.data.value?.items ?? []).filter((r) => r.kind !== 'process')"
            :key="rule.id"
            class="checkbox-label"
            ><input
              type="checkbox"
              :checked="include.automations.includes(rule.id)"
              @change="toggle(include.automations, rule.id)"
            />{{ rule.name }}</label
          >
        </section>
        <section>
          <span class="section-label">Bài kiến thức cho trợ lý AI</span>
          <label v-for="article in articles.data.value?.items ?? []" :key="article.id" class="checkbox-label"
            ><input
              type="checkbox"
              :checked="include.knowledge.includes(article.id)"
              @change="toggle(include.knowledge, article.id)"
            />{{ article.title }}</label
          >
        </section>
      </div>
    </div>
  </section>
</template>
<style scoped>
.pack-meta {
  padding-top: 0;
}
.pack-tabs {
  padding: 0 18px;
}
.pack-look {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
  gap: 22px;
  padding: 18px;
  align-items: start;
}
.pack-form {
  display: grid;
  gap: 16px;
}
fieldset {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
}
legend {
  padding: 0 6px;
  font-weight: 700;
}
.pack-assets {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.pack-asset {
  display: flex;
  gap: 12px;
  align-items: center;
}
.pack-asset > div {
  display: grid;
  gap: 4px;
}
.pack-asset small {
  color: var(--muted);
}
.pack-asset-box {
  display: grid;
  place-items: center;
  flex: none;
  width: 54px;
  height: 54px;
  overflow: hidden;
  border: 1px dashed var(--border-strong);
  border-radius: 12px;
  color: var(--muted);
  background: var(--surface-2);
}
.pack-asset-box.wide {
  width: 96px;
}
.pack-asset-box img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.pack-colors {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) auto auto;
  gap: 6px 14px;
  align-items: center;
}
.pack-color {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.pack-color input[type='color'] {
  width: 32px;
  height: 26px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.pack-color code.muted {
  opacity: 0.6;
}
.pack-color-label {
  font-size: 14px;
}
.pack-contrast {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13.5px;
  color: var(--green-ink);
  background: var(--green-soft);
}
.pack-contrast.bad {
  color: var(--red-ink);
  background: var(--red-soft);
}
.pack-term {
  display: flex;
  gap: 8px;
  align-items: center;
}
.pack-term input {
  flex: 1;
  min-width: 0;
}
.pack-order {
  display: grid;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.pack-order li {
  display: flex;
  gap: 4px;
  align-items: center;
}
.pack-order li label {
  flex: 1;
}
.pack-order li.off {
  opacity: 0.6;
}
.pack-business {
  display: grid;
  gap: 14px;
}
.pack-pick {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 18px;
}
.pack-pick section {
  display: grid;
  gap: 6px;
  align-content: start;
}
.pack-preview {
  position: sticky;
  top: 16px;
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-2);
}
.pack-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 9px;
  overflow: hidden;
}
.segmented button {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  padding: 4px 10px;
  border: 0;
  background: none;
  color: inherit;
  font-size: 13px;
  cursor: pointer;
}
.segmented button.active {
  background: var(--surface);
  font-weight: 700;
}
/* Everything below reads only the preview's own variables. */
.pv-app {
  display: grid;
  grid-template-columns: 130px 1fr;
  min-height: 210px;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--navy);
  background: var(--canvas);
  font-size: 12px;
}
.pv-font-be-vietnam-pro {
  font-family: 'Be Vietnam Pro', sans-serif;
}
.pv-side {
  display: grid;
  gap: 2px;
  align-content: start;
  padding: 10px 8px;
  border-right: 1px solid var(--border);
  background: var(--surface);
}
.pv-brand {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 8px;
}
.pv-brand > span:last-child {
  display: grid;
  min-width: 0;
}
.pv-brand b,
.pv-brand small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pv-brand small {
  color: var(--muted);
  font-size: 10px;
}
.pv-mark {
  display: grid;
  place-items: center;
  flex: none;
  width: 24px;
  height: 24px;
  overflow: hidden;
  border-radius: 7px;
  color: #fff;
  background: var(--teal);
  font-weight: 700;
}
.pv-mark.round {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #fff;
  color: #1e3a5f;
}
.pv-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}
.pv-link {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 4px 6px;
  border-radius: 6px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
}
.pv-link.active {
  color: var(--teal-ink);
  background: var(--teal-soft);
  font-weight: 700;
}
.pv-main {
  padding: 12px;
}
.pv-card {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}
.pv-radius-small .pv-card,
.pv-radius-small .pv-button {
  border-radius: 4px;
}
.pv-radius-large .pv-card {
  border-radius: 16px;
}
.pv-card small {
  color: var(--muted);
}
.pv-card p {
  margin: 2px 0;
}
.pv-card a {
  color: var(--teal-ink);
  text-decoration: underline;
}
.pv-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.pv-button {
  padding: 3px 8px;
  border-radius: 6px;
  color: var(--on-teal, #fff);
  background: var(--teal);
  font-weight: 700;
}
.pv-chip {
  padding: 3px 8px;
  border-radius: 6px;
  color: var(--teal-ink);
  background: var(--teal-soft);
}
.pv-ok {
  padding: 3px 8px;
  border-radius: 6px;
  color: var(--green-ink);
  background: var(--green-soft);
}
.pv-bad {
  padding: 3px 8px;
  border-radius: 6px;
  color: var(--red-ink);
  background: var(--red-soft);
}
.pv-login {
  display: grid;
  gap: 4px;
  justify-items: center;
  padding: 18px 12px;
  border-radius: 12px;
  color: #e8eef8;
  background: linear-gradient(160deg, #183670, #081634);
  text-align: center;
  font-size: 12px;
}
.pv-login-flat {
  background: linear-gradient(160deg, var(--teal-strong), var(--teal));
}
.pv-login-image {
  background: repeating-linear-gradient(45deg, #2b3f5c, #2b3f5c 8px, #24364f 8px, #24364f 16px);
}
.pv-login b {
  font-size: 14px;
}
.pv-login-note {
  margin-top: 4px;
  opacity: 0.8;
}
.pack-login-ground {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  align-items: center;
  margin: 10px 0;
}
.pv-login-button {
  margin-top: 6px;
  padding: 4px 12px;
  border-radius: 999px;
  color: #0f2554;
  background: #fff;
  font-weight: 700;
}
@media (max-width: 1100px) {
  .pack-look {
    grid-template-columns: 1fr;
  }
  .pack-preview {
    position: static;
  }
}
</style>
