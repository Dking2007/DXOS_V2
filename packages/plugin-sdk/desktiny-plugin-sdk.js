// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Frame side of the Desktiny plugin protocol (`desktiny: 1`), for a plugin page shown in Desktiny.
// No dependencies; load it as a module or a plain script (it also sets `window.DesktinyPlugin`).
//
//   const desktiny = DesktinyPlugin.connect({ desktinyOrigin: 'https://desktiny.example.org' })
//   const context = await desktiny.context   // place, record ids, viewer, theme, colours, app name
//   const dossier = await desktiny.api(`/cases/${context.record.case_id}`)
//
// The page runs in a sandboxed frame with an opaque origin: it cannot read Desktiny's cookies or DOM.
// Data comes only through `api()`, with a short-lived token scoped to the viewer and this place.

const PROTOCOL = 1

function connect(options = {}) {
  const parent = window.parent
  const expected = options.desktinyOrigin || null
  const waiting = new Map()
  let session = null
  let resolveContext
  const context = new Promise((resolve) => (resolveContext = resolve))

  function post(message) {
    // The parent is Desktiny; naming its origin (when known) keeps messages from reaching anyone else.
    parent.postMessage({ desktiny: PROTOCOL, ...message }, expected || '*')
  }

  function onMessage(event) {
    if (event.source !== parent) return
    if (expected && event.origin !== expected) return
    const data = event.data
    if (!data || data.desktiny !== PROTOCOL) return
    if (data.type === 'context') {
      applyTheme(data.context)
      resolveContext(data.context)
      if (options.onContext) options.onContext(data.context)
    } else if (data.type === 'token' || data.type === 'error') {
      const pending = waiting.get(data.id)
      if (!pending) return
      waiting.delete(data.id)
      if (data.type === 'token') pending.resolve(data)
      else pending.reject(new Error(data.message || 'Desktiny từ chối cấp phiên.'))
    }
  }
  window.addEventListener('message', onMessage)

  function requestToken() {
    const id = Math.random().toString(36).slice(2)
    return new Promise((resolve, reject) => {
      waiting.set(id, { resolve, reject })
      post({ type: 'token', id })
      setTimeout(() => {
        if (waiting.delete(id)) reject(new Error('Desktiny không trả lời.'))
      }, 10000)
    })
  }

  async function token() {
    // A session lasts minutes; ask again shortly before it ends.
    if (!session || Date.parse(session.expires_at) - Date.now() < 30000) session = await requestToken()
    return session
  }

  async function api(path, init = {}) {
    const current = await token()
    const response = await fetch(current.api_base + path, {
      ...init,
      headers: { ...(init.headers || {}), Authorization: `Bearer ${current.token}`, Accept: 'application/json' },
    })
    if (response.status === 401) session = null
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const error = new Error(body.detail || `Lỗi ${response.status}`)
      error.status = response.status
      error.code = body.code
      throw error
    }
    return body
  }

  function resize(height) {
    post({ type: 'resize', height: Math.ceil(height ?? document.documentElement.scrollHeight) })
  }

  if (options.autoResize !== false && 'ResizeObserver' in window) {
    new ResizeObserver(() => resize()).observe(document.documentElement)
  }
  post({ type: 'ready' })
  return { context, api, token, resize, refreshContext: () => post({ type: 'context' }) }
}

/** Paint the page with Desktiny's theme: `--dk-<name>` variables and `data-theme` on <html>. */
function applyTheme(context) {
  const root = document.documentElement
  root.dataset.theme = context.theme
  for (const [name, value] of Object.entries(context.colors || {})) {
    if (/^[a-z0-9-]+$/.test(name) && /^#[0-9a-fA-F]{3,8}$|^rgb/.test(value)) root.style.setProperty(`--dk-${name}`, value)
  }
  if (context.font) root.style.setProperty('--dk-font', context.font)
}

const DesktinyPlugin = { connect, applyTheme, PROTOCOL }
if (typeof window !== 'undefined') window.DesktinyPlugin = DesktinyPlugin
export { connect, applyTheme, PROTOCOL }
export default DesktinyPlugin
