// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { shallowRef } from 'vue'

export interface ConfirmOptions {
  message: string
  title?: string
  confirmLabel?: string
  /** Destructive action: the confirm button is drawn as dangerous. Cancel always has the focus. */
  danger?: boolean
}
export interface PendingConfirm extends ConfirmOptions {
  resolve: (ok: boolean) => void
}

/** The question on screen; rendered once at the app root by ConfirmHost. */
export const pendingConfirm = shallowRef<PendingConfirm | null>(null)

/** In-app replacement for window.confirm: resolves true only when the person confirms. */
export function confirmDialog(
  options: ConfirmOptions | string,
): Promise<boolean> {
  // A second question replaces the first one, which counts as "no".
  pendingConfirm.value?.resolve(false)
  return new Promise((resolve) => {
    pendingConfirm.value = {
      ...(typeof options === 'string' ? { message: options } : options),
      resolve,
    }
  })
}

export function answerConfirm(ok: boolean) {
  const current = pendingConfirm.value
  pendingConfirm.value = null
  current?.resolve(ok)
}
