// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Screens ask the shell to open the one search box (the top bar's command palette) instead of
// drawing a second search field of their own.
import { ref } from 'vue'

export const paletteRequest = ref<{ text: string; at: number } | null>(null)

export function openPalette(text = '') {
  paletteRequest.value = { text, at: Date.now() }
}
