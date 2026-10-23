import { ref } from 'vue'

export type ThemeChoice = 'light' | 'dark' | 'system'
const KEY = 'dx-workspace-theme'

function stored(): ThemeChoice {
  try {
    const value = window.localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

export const theme = ref<ThemeChoice>(stored())

// `data-theme` is only set for an explicit choice; "system" falls back to the
// prefers-color-scheme rules in the stylesheet.
export function applyTheme(choice: ThemeChoice = theme.value) {
  theme.value = choice
  const root = document.documentElement
  if (choice === 'system') delete root.dataset.theme
  else root.dataset.theme = choice
  try {
    if (choice === 'system') window.localStorage.removeItem(KEY)
    else window.localStorage.setItem(KEY, choice)
  } catch {
    // Private windows may block storage; the choice still applies for this visit.
  }
}

export function isDark() {
  if (theme.value !== 'system') return theme.value === 'dark'
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function cycleTheme() {
  applyTheme(isDark() ? 'light' : 'dark')
}
