<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- Frames of connected plugins for one slot. Each frame is sandboxed without same-origin rights, so
     it can read nothing of Desktiny; it talks to this host over postMessage (protocol `desktiny: 1`):
     "ready" → context (place, record, viewer, theme, the sector pack's colours), "token" → a short-lived
     session token for that context only, "resize" → its height. Commands a frame may give: "toast" (a
     short notice under the plugin's name), "navigate" (an in-app path only), "refresh" (reload what is on
     screen after the plugin wrote), "close" (end the dialog it runs in, with a result) and "confirm"
     (Desktiny asks the person in its own dialog and answers "confirm_result"). Messages count only when
     they come from the frame's own window; the page's CSP frame-src keeps frames from navigating anywhere
     else; device features (`allow`) are only those an administrator approved. -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { useRouter } from 'vue-router'
import { Puzzle } from 'lucide-vue-next'
import ModalDialog from '@dx/web-shared/components/ModalDialog.vue'
import { api } from '../../api'
import { toast } from '../../ui/toast'
import { useSession } from '../../stores/session'
import { brand } from '../../ui/appearance'
import { isDark } from '../../ui/theme'

export interface PluginSlotItem {
  plugin_id: string
  plugin_name: string
  index: number
  title: string
  url: string
  origin: string
  height: number
  /** Device features approved for the plugin, for the iframe's `allow`. */
  allow?: string
}
export type PluginPlace =
  | 'case.side'
  | 'case.tab'
  | 'case.action'
  | 'task.side'
  | 'task.action'
  | 'home.widget'
  | 'page'
  | 'admin.page'
const props = withDefaults(
  defineProps<{
    place: PluginPlace
    context?: { case_id?: string; task_id?: string }
    /** Show only this entry (a plugin's own page). */
    only?: { plugin_id: string; index: number }
    bare?: boolean
  }>(),
  { context: () => ({}), only: undefined, bare: false },
)
const emit = defineEmits<{ close: [result: unknown]; refresh: [] }>()
const session = useSession()
const router = useRouter()
const queryClient = useQueryClient()
// A frame's "confirm" is asked in Desktiny's own dialog, never in one the frame draws to look like ours.
const asking = ref<{ item: PluginSlotItem; id?: string; text: string } | null>(null)
// An in-app path only: one "/", then not "/" or a backslash (which would leave Desktiny).
const INTERNAL_PATH = /^\/(?![/\\])\S*$/
const slots = useQuery({
  queryKey: computed(() => ['plugin-slots', props.place]),
  queryFn: () => api.request<{ items: PluginSlotItem[] }>(`/plugin-slots?slot=${props.place}`).then((r) => r.items),
  staleTime: 60_000,
})
const items = computed(() =>
  (slots.data.value ?? []).filter(
    (item) => !props.only || (item.plugin_id === props.only.plugin_id && item.index === props.only.index),
  ),
)
const frames = ref<Record<string, HTMLIFrameElement | null>>({})
const heights = reactive<Record<string, number>>({})
const COLOR_VARS = ['navy', 'muted', 'canvas', 'surface', 'surface-2', 'border', 'teal', 'teal-strong', 'teal-soft',
  'teal-ink', 'red', 'green-ink']  // prettier-ignore

function keyOf(item: PluginSlotItem) {
  return `${item.plugin_id}:${item.index}`
}
function themeColors() {
  const style = getComputedStyle(document.documentElement)
  return Object.fromEntries(COLOR_VARS.map((name) => [name, style.getPropertyValue(`--${name}`).trim()]))
}
function contextFor(item: PluginSlotItem) {
  return {
    place: props.place,
    plugin_id: item.plugin_id,
    record: { ...props.context },
    viewer: session.user ? { id: session.user.id, display_name: session.user.display_name } : null,
    theme: isDark() ? 'dark' : 'light',
    colors: themeColors(),
    font: getComputedStyle(document.documentElement).fontFamily,
    app: { name: brand.value.name, org: brand.value.org },
  }
}
function send(item: PluginSlotItem, message: Record<string, unknown>) {
  // Sandboxed frames have an opaque origin, so "*" is the only target; the window itself is the check.
  frames.value[keyOf(item)]?.contentWindow?.postMessage({ desktiny: 1, ...message }, '*')
}
async function onMessage(event: MessageEvent) {
  const item = items.value.find((entry) => frames.value[keyOf(entry)]?.contentWindow === event.source)
  const data = event.data as {
    desktiny?: number
    type?: string
    height?: number
    id?: string
    text?: unknown
    tone?: unknown
    path?: unknown
    result?: unknown
  }
  if (!item || !data || data.desktiny !== 1) return
  const text = typeof data.text === 'string' ? data.text.slice(0, 300) : ''
  if (data.type === 'toast' && text) {
    const notice = `${item.plugin_name}: ${text}`
    if (data.tone === 'error') toast.error(notice)
    else toast.success(notice)
    return
  }
  if (data.type === 'navigate') {
    if (typeof data.path === 'string' && INTERNAL_PATH.test(data.path)) void router.push(data.path)
    return
  }
  if (data.type === 'refresh') {
    await queryClient.invalidateQueries()
    emit('refresh')
    return
  }
  if (data.type === 'close') {
    emit('close', data.result ?? null)
    return
  }
  if (data.type === 'confirm' && text) {
    asking.value = { item, id: data.id, text }
    return
  }
  if (data.type === 'ready' || data.type === 'context') {
    send(item, { type: 'context', context: contextFor(item) })
  } else if (data.type === 'resize' && typeof data.height === 'number') {
    heights[keyOf(item)] = Math.min(1200, Math.max(80, Math.round(data.height)))
  } else if (data.type === 'token') {
    try {
      const issued = await api.request<{ token: string; expires_at: string; api_base: string }>('/plugin-sessions', {
        method: 'POST',
        body: JSON.stringify({ plugin_id: item.plugin_id, slot: props.place, ...props.context }),
      })
      send(item, {
        type: 'token',
        id: data.id,
        token: issued.token,
        expires_at: issued.expires_at,
        api_base: window.location.origin + issued.api_base,
      })
    } catch {
      send(item, { type: 'error', id: data.id, message: 'Không cấp được phiên cho plugin.' })
    }
  }
}
function answer(ok: boolean) {
  if (!asking.value) return
  send(asking.value.item, { type: 'confirm_result', id: asking.value.id, ok })
  asking.value = null
}
onMounted(() => window.addEventListener('message', onMessage))
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
</script>
<template>
  <template v-for="item in items" :key="keyOf(item)">
    <section v-if="!bare" class="card plugin-frame-card" :aria-label="`${item.title} (plugin ${item.plugin_name})`">
      <header class="card-header plugin-frame-head">
        <h3><Puzzle :size="15" /> {{ item.title }}</h3>
        <small class="muted" :title="item.origin">{{ item.plugin_name }}</small>
      </header>
      <iframe
        :ref="(el) => (frames[keyOf(item)] = el as HTMLIFrameElement | null)"
        class="plugin-frame"
        :src="item.url"
        :title="item.title"
        :style="{ height: `${heights[keyOf(item)] ?? item.height}px` }"
        sandbox="allow-scripts allow-forms allow-popups"
        :allow="item.allow || undefined"
        referrerpolicy="no-referrer"
        loading="lazy"
      />
    </section>
    <iframe
      v-else
      :ref="(el) => (frames[keyOf(item)] = el as HTMLIFrameElement | null)"
      class="plugin-frame bare"
      :src="item.url"
      :title="item.title"
      :style="{ height: `${heights[keyOf(item)] ?? item.height}px` }"
      sandbox="allow-scripts allow-forms allow-popups"
      :allow="item.allow || undefined"
      referrerpolicy="no-referrer"
    />
  </template>
  <ModalDialog v-if="asking" :title="`Xác nhận (${asking.item.plugin_name})`" @close="answer(false)">
    <div class="stack">
      <p class="prewrap">{{ asking.text }}</p>
      <div class="form-actions">
        <button type="button" class="button secondary" @click="answer(false)">Không</button
        ><button type="button" class="button" @click="answer(true)">Đồng ý</button>
      </div>
    </div>
  </ModalDialog>
</template>
<style scoped>
.plugin-frame-card {
  overflow: hidden;
}
.plugin-frame-head h3 {
  display: flex;
  gap: 6px;
  align-items: center;
}
.plugin-frame {
  display: block;
  width: 100%;
  border: 0;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.plugin-frame.bare {
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
</style>
