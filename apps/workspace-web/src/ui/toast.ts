import { reactive } from 'vue'
import { errorText } from '@dx/web-shared/api.ts'

export type ToastKind = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  kind: ToastKind
  text: string
  action?: { label: string; run: () => void }
}

let next = 1
export const toasts = reactive<Toast[]>([])

export function dismiss(id: number) {
  const index = toasts.findIndex((item) => item.id === id)
  if (index >= 0) toasts.splice(index, 1)
}

function push(kind: ToastKind, text: string, action?: Toast['action']) {
  const id = next++
  toasts.push({ id, kind, text, action })
  if (toasts.length > 4) toasts.shift()
  // Errors stay a little longer: people need time to read what went wrong.
  setTimeout(() => dismiss(id), kind === 'error' ? 8000 : 4000)
  return id
}

export const toast = {
  success: (text: string, action?: Toast['action']) => push('success', text, action),
  info: (text: string, action?: Toast['action']) => push('info', text, action),
  error: (error: unknown) => push('error', typeof error === 'string' ? error : errorText(error)),
}
