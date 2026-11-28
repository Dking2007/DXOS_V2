// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { afterEach, describe, expect, it } from 'vitest'
import { answerConfirm, pendingConfirm } from '@dx/web-shared/confirm.ts'
import {
  SIDEBAR_KEY,
  SIDEBAR_WIDE_KEY,
  isCollapsed,
  readPrefs,
  toggleLabel,
  toggled,
  writePrefs,
} from './sidebar'
import { allowedOn, mostScrolled, nextVisible, scrollBehavior } from './backToTop'
import { confirmLeaveAll, hasUnsavedChanges, registerDirty, resetLeaveConsent } from './unsaved'
import { menuStep } from './popover'

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial))
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  }
}

describe('sidebar collapse', () => {
  it('folds wide pages by default but lets the person unfold them', () => {
    let prefs = readPrefs(memoryStorage())
    expect(isCollapsed(prefs, false)).toBe(false)
    expect(isCollapsed(prefs, true)).toBe(true)
    prefs = toggled(prefs, true)
    expect(isCollapsed(prefs, true)).toBe(false)
    // The choice on the canvas does not change ordinary pages, and the other way round.
    expect(isCollapsed(prefs, false)).toBe(false)
    prefs = toggled(prefs, false)
    expect(isCollapsed(prefs, false)).toBe(true)
    expect(isCollapsed(prefs, true)).toBe(false)
  })

  it('remembers both choices separately', () => {
    const storage = memoryStorage()
    writePrefs(storage, toggled(readPrefs(storage), true))
    expect(storage.data.get(SIDEBAR_WIDE_KEY)).toBe('0')
    expect(storage.data.get(SIDEBAR_KEY)).toBe('0')
    expect(readPrefs(storage)).toEqual({ normal: false, wide: false })
    // Keeps the old key so earlier choices on ordinary pages survive the upgrade.
    expect(readPrefs(memoryStorage({ [SIDEBAR_KEY]: '1' }))).toEqual({ normal: true, wide: null })
  })

  it('survives blocked storage', () => {
    const blocked = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('blocked')
      },
    }
    expect(readPrefs(blocked)).toEqual({ normal: false, wide: null })
    expect(() => writePrefs(blocked, { normal: true, wide: true })).not.toThrow()
  })

  it('labels the button by what it will do', () => {
    expect(toggleLabel(true)).toBe('Mở rộng thanh bên')
    expect(toggleLabel(false)).toBe('Thu gọn thanh bên')
  })
})

describe('back to top', () => {
  it('appears after one screen and hides a little earlier on the way up', () => {
    expect(nextVisible(false, { top: 700, height: 800 })).toBe(false)
    expect(nextVisible(false, { top: 801, height: 800 })).toBe(true)
    expect(nextVisible(true, { top: 700, height: 800 })).toBe(true)
    expect(nextVisible(true, { top: 590, height: 800 })).toBe(false)
    expect(nextVisible(true, { top: 500, height: 0 })).toBe(false)
  })

  it('follows whichever scroller actually moved', () => {
    const window = { name: 'window', top: 0, height: 900 }
    const main = { name: 'main', top: 1400, height: 820 }
    expect(mostScrolled([window, main])?.name).toBe('main')
    expect(mostScrolled([{ ...window, top: 50 }, { ...main, top: 0 }])?.name).toBe('window')
    expect(mostScrolled([])).toBeUndefined()
  })

  it('jumps instead of gliding when motion is reduced, and stays off the canvas', () => {
    expect(scrollBehavior(true)).toBe('auto')
    expect(scrollBehavior(false)).toBe('smooth')
    expect(allowedOn({ wide: true })).toBe(false)
    expect(allowedOn({})).toBe(true)
  })
})

describe('unsaved changes on logout', () => {
  afterEach(() => {
    resetLeaveConsent()
    answerConfirm(false)
  })

  it('asks only when something on screen is unsaved, and only once', async () => {
    let dirty = false
    const unregister = registerDirty(() => dirty)
    expect(hasUnsavedChanges()).toBe(false)
    await expect(confirmLeaveAll()).resolves.toBe(true)
    expect(pendingConfirm.value).toBeNull()
    dirty = true
    const first = confirmLeaveAll()
    expect(pendingConfirm.value?.danger).toBe(true)
    answerConfirm(true)
    await expect(first).resolves.toBe(true)
    await expect(confirmLeaveAll()).resolves.toBe(true)
    expect(pendingConfirm.value).toBeNull()
    unregister()
    expect(hasUnsavedChanges()).toBe(false)
  })

  it('stays put when the person cancels', async () => {
    const unregister = registerDirty(() => true)
    const leaving = confirmLeaveAll()
    answerConfirm(false)
    await expect(leaving).resolves.toBe(false)
    unregister()
  })
})

describe('menu keyboard', () => {
  it('moves through items with the arrows and wraps around', () => {
    expect(menuStep('ArrowDown', -1, 4)).toBe(0)
    expect(menuStep('ArrowDown', 3, 4)).toBe(0)
    expect(menuStep('ArrowUp', -1, 4)).toBe(3)
    expect(menuStep('ArrowUp', 0, 4)).toBe(3)
    expect(menuStep('Home', 2, 4)).toBe(0)
    expect(menuStep('End', 0, 4)).toBe(3)
    expect(menuStep('Tab', 0, 4)).toBe(-1)
    expect(menuStep('ArrowDown', -1, 0)).toBe(-1)
  })
})
