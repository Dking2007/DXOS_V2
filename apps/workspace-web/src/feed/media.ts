// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { computed, onBeforeUnmount, ref } from 'vue'
import type { PostMedia } from '@dx/web-shared/types.ts'
import { errorText } from '@dx/web-shared/api.ts'
import { uploadWithProgress } from '../chat/upload'

export const MEDIA_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,video/mp4,video/webm,video/quicktime'
export const MAX_MEDIA = 10
export const MAX_MEDIA_BYTES = 50 * 1024 * 1024
const ALLOWED = new Set(MEDIA_ACCEPT.split(','))

/** Why a file cannot go into a post, or null when it can. */
export function mediaProblem(file: { type: string; size: number }): string | null {
  if (!ALLOWED.has(file.type)) return 'Chỉ đăng được ảnh (PNG, JPEG, GIF, WebP) và video (MP4, WebM, MOV).'
  if (file.size > MAX_MEDIA_BYTES) return 'Tệp lớn hơn 50 MB.'
  if (!file.size) return 'Tệp rỗng.'
  return null
}

/** How many tiles a post shows before "+N", and which layout the grid uses. */
export function gridLayout(count: number) {
  const shown = Math.min(count, 4)
  return { shown, more: count - shown, layout: `count-${shown}` }
}

export interface PendingMedia {
  key: string
  file: File
  kind: 'image' | 'video'
  preview: string
  progress: number
  media?: PostMedia
  error?: string
  abort?: () => void
}

/** Pictures and videos picked in the composer, uploaded straight away with progress. */
export function useMediaUploads(csrf: () => string) {
  const items = ref<PendingMedia[]>([])
  const uploading = computed(() => items.value.some((item) => !item.media && !item.error))
  const failed = computed(() => items.value.some((item) => item.error))
  const ids = computed(() => items.value.flatMap((item) => (item.media ? [item.media.id] : [])))

  function add(files: Iterable<File>) {
    const rejected: string[] = []
    for (const file of files) {
      if (items.value.length >= MAX_MEDIA) {
        rejected.push(`Mỗi bài tối đa ${MAX_MEDIA} ảnh/video.`)
        break
      }
      const problem = mediaProblem(file)
      if (problem) {
        rejected.push(`${file.name}: ${problem}`)
        continue
      }
      items.value.push({
        key: crypto.randomUUID(),
        file,
        kind: file.type.startsWith('video/') ? 'video' : 'image',
        preview: URL.createObjectURL(file),
        progress: 0,
      })
      const entry = items.value.at(-1)!
      const job = uploadWithProgress<PostMedia>('/post-attachments', file, csrf(), (fraction) => {
        entry.progress = fraction
      })
      entry.abort = job.abort
      job.promise.then(
        (media) => (entry.media = media),
        (error) => (entry.error = errorText(error)),
      )
    }
    return rejected
  }
  function remove(key: string) {
    const item = items.value.find((entry) => entry.key === key)
    if (!item) return
    if (!item.media && !item.error) item.abort?.()
    URL.revokeObjectURL(item.preview)
    items.value = items.value.filter((entry) => entry.key !== key)
  }
  function clear() {
    for (const item of [...items.value]) remove(item.key)
  }
  onBeforeUnmount(clear)
  return { items, uploading, failed, ids, add, remove, clear }
}
