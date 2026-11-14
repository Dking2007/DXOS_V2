<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Sector packs (gói ngành): what is installed, which look is in force, packs shipped with the
     release, uploading a .zip with a preview before anything changes, and the pack builder. -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  AlertTriangle,
  Download,
  Package,
  Palette,
  Pencil,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import { api } from '../api'
import { errorText, formatDate } from '@dx/web-shared/api.ts'
import StatePanel from '@dx/web-shared/components/StatePanel.vue'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import PackBuilder from '../components/packs/PackBuilder.vue'
import type { LocalPack, PackLimits } from '../components/packs/PackBuilder.vue'
import { applyAppearance } from '../ui/appearance'
import type { AppearanceLook, AppearanceState } from '../ui/appearance'
import { toast } from '../ui/toast'

interface Counts {
  processes: number
  forms: number
  templates: number
  automations: number
  knowledge: number
}
interface InstalledPack {
  pack_id: string
  name: string
  version: string
  source: 'file' | 'builtin' | 'local'
  description: string
  license: string
  has_appearance: boolean
  appearance: AppearanceLook | null
  appearance_active: boolean
  counts: Counts
  includes: LocalPack['includes']
  removable: boolean
  revision: number
  updated_at: string
}
interface AvailablePack {
  pack_id: string
  name: string
  version: string
  description: string
  installed_version: string | null
  has_appearance: boolean
  counts: Counts
}
interface Listing {
  installed: InstalledPack[]
  available: AvailablePack[]
  appearance_pack_id: string | null
  appearance_revision: number
  limits: PackLimits
}
interface Preview {
  pack: { id: string; name: string; version: string; description: string; license: string; authors: string[] }
  upgrade_from: string | null
  appearance: AppearanceLook | null
  adds: Record<'processes' | 'forms' | 'templates' | 'automations' | 'knowledge', string[]>
  conflicts: string[]
  warnings: string[]
}

const queryClient = useQueryClient()
const listing = useQuery({ queryKey: ['packs'], queryFn: () => api.request<Listing>('/packs') })
const busy = ref(false)
const building = ref<LocalPack | 'new' | null>(null)
const preview = ref<Preview | null>(null)
const previewError = ref<unknown>(null)
const pending = ref<{ file?: File; builtin?: string } | null>(null)
const activate = ref(true)
const removing = ref<InstalledPack | null>(null)

const SOURCE: Record<InstalledPack['source'], string> = {
  builtin: 'Có sẵn',
  file: 'Tải lên',
  local: 'Của cơ quan',
}
const KIND_LABEL: Record<keyof Counts, string> = {
  processes: 'quy trình',
  forms: 'biểu mẫu',
  templates: 'mẫu quy trình',
  automations: 'luồng tự động',
  knowledge: 'bài kiến thức',
}
const active = computed(() => listing.data.value?.installed.find((pack) => pack.appearance_active) ?? null)

function countText(counts: Counts) {
  return (Object.keys(KIND_LABEL) as (keyof Counts)[])
    .filter((key) => counts[key])
    .map((key) => `${counts[key]} ${KIND_LABEL[key]}`)
}
async function refresh() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ['packs'] }),
    queryClient.invalidateQueries({ queryKey: ['pack-templates'] }),
    queryClient.invalidateQueries({ queryKey: ['automations'] }),
  ])
  // The look in force may have changed; repaint the app with it.
  applyAppearance(await api.request<AppearanceState>('/appearance'))
}
function formOf(source: { file?: File; builtin?: string }, withActivate = false) {
  const body = new FormData()
  if (source.file) body.append('file', source.file)
  if (source.builtin) body.append('builtin', source.builtin)
  if (withActivate) body.append('activate', activate.value ? 'true' : 'false')
  return body
}
async function openPreview(source: { file?: File; builtin?: string }) {
  pending.value = source
  preview.value = null
  previewError.value = null
  activate.value = true
  try {
    preview.value = await api.request<Preview>('/packs/preview', { method: 'POST', body: formOf(source) })
  } catch (cause) {
    previewError.value = cause
  }
}
function pickFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) void openPreview({ file })
}
async function install() {
  if (!pending.value) return
  busy.value = true
  try {
    const result = await api.request<{ notes: string[] }>('/packs', {
      method: 'POST',
      body: formOf(pending.value, !!preview.value?.appearance),
    })
    toast.success(preview.value?.upgrade_from ? 'Đã nâng cấp gói.' : 'Đã cài gói.')
    for (const note of result.notes) toast.success(note)
    preview.value = null
    pending.value = null
    await refresh()
  } catch (cause) {
    previewError.value = cause
  } finally {
    busy.value = false
  }
}
async function useLook(packId: string | null) {
  busy.value = true
  try {
    await api.request('/appearance', {
      method: 'PUT',
      body: JSON.stringify({ pack_id: packId, expected_revision: listing.data.value?.appearance_revision }),
    })
    toast.success(packId ? 'Đã áp dụng giao diện của gói.' : 'Đã về giao diện mặc định.')
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function remove() {
  if (!removing.value) return
  busy.value = true
  try {
    const result = await api.request<{ notes: string[] }>(
      `/packs/${encodeURIComponent(removing.value.pack_id)}`,
      { method: 'DELETE' },
    )
    toast.success(`Đã gỡ “${removing.value.name}”.`)
    for (const note of result.notes) toast.success(note)
    removing.value = null
    await refresh()
  } catch (cause) {
    toast.error(cause)
  } finally {
    busy.value = false
  }
}
async function exportPack(pack: InstalledPack) {
  try {
    const response = await fetch(`/workspace/v1/packs/${encodeURIComponent(pack.pack_id)}/export`, {
      credentials: 'same-origin',
    })
    if (!response.ok) throw new Error('Không xuất được gói.')
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = `${pack.pack_id}-${pack.version}.zip`
    link.click()
    URL.revokeObjectURL(url)
  } catch (cause) {
    toast.error(cause)
  }
}
function edit(pack: InstalledPack) {
  building.value = {
    pack_id: pack.pack_id,
    name: pack.name,
    version: pack.version,
    description: pack.description,
    appearance: pack.appearance,
    includes: pack.includes ?? {},
    revision: pack.revision,
  }
}
async function saved() {
  building.value = null
  await refresh()
}
/** A few swatches of a pack's main colours, for the cards. */
function swatches(look: AppearanceLook | null) {
  const light = look?.colors?.light ?? {}
  return ['teal', 'teal-soft', 'teal-ink', 'navy'].map((key) => light[key]).filter(Boolean) as string[]
}
</script>
<template>
  <header class="page-head compact">
    <h1 class="sr-only">Gói ngành</h1>
    <div class="page-actions">
      <label class="button secondary"
        ><Upload :size="17" />Tải gói lên (.zip)<input
          type="file"
          accept=".zip,application/zip"
          class="sr-only"
          @change="pickFile"
      /></label>
      <button class="button" type="button" @click="building = 'new'"><Plus :size="17" />Tạo gói của cơ quan</button>
    </div>
  </header>

  <PackBuilder
    v-if="building && listing.data.value"
    :key="building === 'new' ? 'new' : building.pack_id"
    :pack="building === 'new' ? null : building"
    :limits="listing.data.value.limits"
    @saved="saved"
    @close="building = null"
  />

  <template v-else>
    <StatePanel
      v-if="listing.isPending.value || listing.error.value"
      :loading="listing.isPending.value"
      :error="listing.error.value"
      @retry="listing.refetch()"
    />
    <template v-else-if="listing.data.value">
      <section class="card pack-current">
        <span class="pack-current-icon"><Palette :size="22" /></span>
        <div class="grow">
          <small class="muted">Giao diện đang dùng</small>
          <strong>{{ active ? active.name : 'Mặc định của Desktiny' }}</strong>
          <small v-if="active?.appearance?.app_name" class="muted"
            >{{ active.appearance.app_name
            }}<template v-if="active.appearance.org_name"> · {{ active.appearance.org_name }}</template></small
          >
        </div>
        <button v-if="active" class="button secondary small" :disabled="busy" @click="useLook(null)">
          <RotateCcw :size="15" />Về giao diện mặc định
        </button>
      </section>

      <section class="card">
        <header class="card-header"><h2>Gói đã cài</h2></header>
        <div class="pack-list">
          <article v-for="pack in listing.data.value.installed" :key="pack.pack_id" class="pack-item">
            <span class="pack-icon" :class="{ look: pack.has_appearance }"
              ><span v-if="swatches(pack.appearance).length" class="pack-swatches"
                ><i v-for="color in swatches(pack.appearance)" :key="color" :style="{ background: color }" /></span
              ><Package v-else :size="20"
            /></span>
            <div class="grow">
              <div class="pack-title">
                <strong>{{ pack.name }}</strong>
                <span class="tag">{{ SOURCE[pack.source] }}</span>
                <span v-if="pack.appearance_active" class="tag pack-active">Đang dùng giao diện</span>
              </div>
              <small class="muted mono">{{ pack.pack_id }} · {{ pack.version }} · {{ pack.license }}</small>
              <p v-if="pack.description">{{ pack.description }}</p>
              <small class="muted"
                >{{ [...(pack.has_appearance ? ['giao diện'] : []), ...countText(pack.counts)].join(' · ') || 'Chưa có nội dung' }}
                · cập nhật {{ formatDate(pack.updated_at, true) }}</small
              >
            </div>
            <div class="pack-actions">
              <button
                v-if="pack.has_appearance && !pack.appearance_active"
                class="button small"
                :disabled="busy"
                @click="useLook(pack.pack_id)"
              >
                <Palette :size="15" />Dùng giao diện này
              </button>
              <button v-if="pack.source === 'local'" class="button secondary small" @click="edit(pack)">
                <Pencil :size="15" />Sửa
              </button>
              <button v-if="pack.source !== 'builtin' || pack.removable" class="button ghost small" @click="exportPack(pack)">
                <Download :size="15" />Xuất
              </button>
              <button v-if="pack.removable" class="button ghost small" @click="removing = pack">
                <Trash2 :size="15" />Gỡ
              </button>
            </div>
          </article>
        </div>
      </section>

      <section v-if="listing.data.value.available.length" class="card">
        <header class="card-header"><h2>Gói có sẵn trong bản phát hành</h2></header>
        <div class="pack-list">
          <article v-for="pack in listing.data.value.available" :key="pack.pack_id" class="pack-item">
            <span class="pack-icon"><Sparkles :size="20" /></span>
            <div class="grow">
              <div class="pack-title">
                <strong>{{ pack.name }}</strong
                ><span v-if="pack.installed_version" class="tag">Có bản mới {{ pack.version }}</span>
              </div>
              <small class="muted mono">{{ pack.pack_id }} · {{ pack.version }}</small>
              <p v-if="pack.description">{{ pack.description }}</p>
              <small class="muted">{{
                [...(pack.has_appearance ? ['giao diện'] : []), ...countText(pack.counts)].join(' · ')
              }}</small>
            </div>
            <div class="pack-actions">
              <button class="button small" @click="openPreview({ builtin: pack.pack_id })">
                {{ pack.installed_version ? 'Xem và nâng cấp' : 'Xem và cài' }}
              </button>
            </div>
          </article>
        </div>
      </section>
      <p class="muted pack-foot">
        Gói ngành không chứa mã. Gỡ gói thì về đúng giao diện và nghiệp vụ mặc định; quy trình đã có hồ sơ chỉ ngừng
        phát hành, không bị xoá. Cách viết gói: <code>docs/packs.md</code>.
      </p>
    </template>
  </template>

  <ModalDialog
    v-if="pending"
    :title="preview?.upgrade_from ? 'Nâng cấp gói ngành' : 'Cài gói ngành'"
    wide
    @close="
      () => {
        if (!busy) pending = null
      }
    "
  >
    <div v-if="previewError" class="notice error error-inline">{{ errorText(previewError) }}</div>
    <StatePanel v-else-if="!preview" :loading="true" />
    <div v-if="preview" class="stack">
      <div>
        <strong>{{ preview.pack.name }}</strong>
        <small class="muted mono">
          · {{ preview.pack.id }} ·
          <template v-if="preview.upgrade_from">{{ preview.upgrade_from }} → </template>{{ preview.pack.version }} ·
          {{ preview.pack.license }}</small
        >
        <p v-if="preview.pack.description">{{ preview.pack.description }}</p>
      </div>
      <div v-if="preview.appearance" class="pack-preview-look">
        <span class="pack-swatches big"
          ><i v-for="color in swatches(preview.appearance)" :key="color" :style="{ background: color }"
        /></span>
        <div>
          <strong>Giao diện: {{ preview.appearance.app_name || 'giữ tên Desktiny' }}</strong>
          <small v-if="preview.appearance.org_name" class="muted">{{ preview.appearance.org_name }}</small>
          <small v-if="Object.keys(preview.appearance.terminology ?? {}).length" class="muted"
            >Từ ngữ:
            {{
              Object.entries(preview.appearance.terminology ?? {})
                .map(([from, to]) => `${from} → ${to}`)
                .join(', ')
            }}</small
          >
          <small v-if="preview.appearance.menu?.hide?.length" class="muted"
            >Ẩn khỏi menu: {{ preview.appearance.menu.hide.join(', ') }}</small
          >
        </div>
      </div>
      <div class="pack-adds">
        <template v-for="(items, kind) in preview.adds" :key="kind">
          <div v-if="items.length">
            <span class="section-label">{{ items.length }} {{ KIND_LABEL[kind] }}</span>
            <ul>
              <li v-for="item in items" :key="item">{{ item }}</li>
            </ul>
          </div>
        </template>
      </div>
      <div v-if="preview.conflicts.length || preview.warnings.length" class="notice warning">
        <AlertTriangle :size="18" />
        <ul>
          <li v-for="item in [...preview.conflicts, ...preview.warnings]" :key="item">{{ item }}</li>
        </ul>
      </div>
      <label v-if="preview.appearance" class="checkbox-label"
        ><input v-model="activate" type="checkbox" /> Dùng giao diện của gói ngay sau khi cài (thay giao diện đang
        dùng)</label
      >
      <small class="muted"
        >Luồng tự động được cài ở trạng thái tắt. Quy trình chỉ định người cụ thể được cài dạng nháp để chọn lại
        người.</small
      >
      <div class="form-actions">
        <button type="button" class="button secondary" :disabled="busy" @click="pending = null">Hủy</button
        ><button type="button" class="button" :disabled="busy" @click="install">
          {{ busy ? 'Đang cài…' : preview.upgrade_from ? 'Nâng cấp' : 'Cài gói' }}
        </button>
      </div>
    </div>
  </ModalDialog>

  <ModalDialog v-if="removing" title="Gỡ gói ngành" @close="removing = null">
    <div class="stack">
      <p>
        Gỡ <strong>{{ removing.name }}</strong>?
      </p>
      <p v-if="removing.source === 'local'" class="muted">
        Gói của cơ quan chỉ trỏ tới quy trình, luồng và bài kiến thức sẵn có; gỡ gói không xoá chúng.
      </p>
      <p v-else class="muted">
        Những gì gói đã thêm được gỡ theo. Quy trình hoặc luồng đã có hồ sơ, lượt chạy thì chỉ ngừng sử dụng, không xoá.
      </p>
      <p v-if="removing.appearance_active" class="muted">Ứng dụng sẽ về giao diện mặc định.</p>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="removing = null">Hủy</button
        ><button type="button" class="button danger" :disabled="busy" @click="remove">
          {{ busy ? 'Đang gỡ…' : 'Gỡ gói' }}
        </button>
      </div>
    </div>
  </ModalDialog>
</template>
<style scoped>
.pack-current {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 18px;
}
.pack-current .grow {
  display: grid;
}
.pack-current-icon,
.pack-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  color: var(--teal-ink);
  background: var(--teal-soft);
}
.pack-list {
  display: grid;
}
.pack-item {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: flex-start;
  padding: 14px 18px;
  border-top: 1px solid var(--border-soft);
}
.pack-item .grow {
  display: grid;
  gap: 2px;
  flex: 1;
  min-width: 220px;
}
.pack-item p {
  margin: 4px 0;
}
.pack-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.pack-active {
  color: var(--green-ink);
  background: var(--green-soft);
}
.pack-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pack-swatches {
  display: grid;
  grid-template-columns: 1fr 1fr;
  width: 30px;
  height: 30px;
  overflow: hidden;
  border-radius: 8px;
}
.pack-swatches.big {
  width: 48px;
  height: 48px;
  flex: none;
  border-radius: 12px;
}
.pack-swatches i {
  display: block;
}
.pack-preview-look {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.pack-preview-look > div {
  display: grid;
  gap: 2px;
}
.pack-adds {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.pack-adds ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.notice ul {
  margin: 0;
  padding-left: 18px;
}
.pack-foot {
  margin-top: 16px;
  font-size: 13.5px;
}
</style>
