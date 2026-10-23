import { ApiError, csrfCookie, newIntent } from '@dx/web-shared/api.ts'
import type { ChatAttachment } from '@dx/web-shared/types.ts'

export const MAX_FILE_BYTES = 50 * 1024 * 1024
export const ACCEPT =
  'image/png,image/jpeg,image/gif,image/webp,video/mp4,video/webm,video/quicktime,audio/mpeg,audio/ogg,audio/wav,' +
  '.pdf,.txt,.csv,.docx,.xlsx,.pptx,.zip,.m4v,.mov'

/**
 * Upload one chat attachment with progress. `fetch` cannot report upload progress, so this
 * uses XMLHttpRequest with the same cookie session and CSRF header as the API client.
 */
export function uploadAttachment(
  conversationId: string,
  file: File,
  csrf: string,
  onProgress: (fraction: number) => void,
): { promise: Promise<ChatAttachment>; abort: () => void } {
  const xhr = new XMLHttpRequest()
  const promise = new Promise<ChatAttachment>((resolve, reject) => {
    xhr.open('POST', `/workspace/v1/conversations/${conversationId}/attachments`)
    xhr.withCredentials = true
    xhr.setRequestHeader('X-CSRF-Token', csrf || csrfCookie('workspace'))
    xhr.setRequestHeader('Idempotency-Key', newIntent())
    xhr.upload.onprogress = (event) => event.lengthComputable && onProgress(event.loaded / event.total)
    xhr.onload = () => {
      let body: Record<string, unknown> = {}
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // A non-JSON error page still becomes a readable error below.
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as unknown as ChatAttachment)
      else
        reject(
          new ApiError(
            xhr.status,
            String(body.code ?? 'upload_failed'),
            typeof body.detail === 'string' ? body.detail : 'Không tải được tệp lên.',
          ),
        )
    }
    xhr.onerror = () => reject(new ApiError(0, 'network_error', 'Mất kết nối khi tải tệp lên.'))
    xhr.onabort = () => reject(new ApiError(0, 'aborted', 'Đã hủy tải lên.'))
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
  return { promise, abort: () => xhr.abort() }
}

export function fileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** Stable pastel colour per person, so the same sender always looks the same. */
export function avatarColor(seed: string) {
  let hash = 0
  for (const char of seed) hash = (hash * 31 + char.charCodeAt(0)) | 0
  const hues = [188, 205, 262, 330, 24, 145, 46, 220]
  return `hsl(${hues[Math.abs(hash) % hues.length]} 55% 46%)`
}

export function initials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(-2)
    .map((word) => word[0])
    .join('')
    .toUpperCase()
}

export function dayLabel(iso: string) {
  const date = new Date(iso)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  if (same(date, today)) return 'Hôm nay'
  if (same(date, yesterday)) return 'Hôm qua'
  return date.toLocaleDateString('vi-VN', { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function timeLabel(iso: string) {
  return new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

/** Short time for the conversation list: clock today, weekday this week, date otherwise. */
export function listTime(iso: string) {
  const date = new Date(iso)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) return timeLabel(iso)
  if (now.getTime() - date.getTime() < 6 * 86400000)
    return date.toLocaleDateString('vi-VN', { weekday: 'short' })
  return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' })
}
