// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Frame side of the Desktiny plugin protocol (`desktiny: 1`), for a plugin page shown in Desktiny.
// No dependencies; load it as a module or a plain script (it also sets `window.DesktinyPlugin`).
//
//   const desktiny = DesktinyPlugin.connect({ desktinyOrigin: 'https://desktiny.example.org' })
//   // A packaged plugin (pages inside its .zip, served by Desktiny) can leave `desktinyOrigin` out.
//   const context = await desktiny.context   // place, record ids, viewer, theme, colours, app name
//   const dossier = await desktiny.api(`/cases/${context.record.case_id}`)
//   desktiny.toast('Đã ký số')            // also: navigate('/cases/…'), refresh(), close(result)
//   if (await desktiny.confirm('Ký văn bản này?')) { … }   // asked in Desktiny's own dialog
//
// The page runs in a sandboxed frame with an opaque origin: it cannot read Desktiny's cookies or DOM.
// Data comes only through `api()`, with a short-lived token scoped to the viewer and this place.

const PROTOCOL = 1

function connect(options = {}) {
  const parent = window.parent
  const expected = options.desktinyOrigin || servedOrigin()
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
    } else if (data.type === 'confirm_result') {
      const pending = waiting.get(data.id)
      if (!pending) return
      waiting.delete(data.id)
      pending.resolve(data.ok === true)
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
    const id = newId()
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
    const headers = { ...(init.headers || {}), Authorization: `Bearer ${current.token}`, Accept: 'application/json' }
    // Writes need an Idempotency-Key; one per call unless the page passes its own to retry safely.
    if (init.method && init.method !== 'GET' && !headers['Idempotency-Key']) headers['Idempotency-Key'] = newId()
    if (init.body && typeof init.body !== 'string' && !(init.body instanceof FormData)) {
      init = { ...init, body: JSON.stringify(init.body) }
      headers['Content-Type'] = 'application/json'
    }
    const response = await fetch(current.api_base + path, { ...init, headers })
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

  /** Commands Desktiny carries out for the frame. */
  const toast = (text, tone = 'success') => post({ type: 'toast', text: String(text), tone })
  const navigate = (path) => post({ type: 'navigate', path })
  const refresh = () => post({ type: 'refresh' })
  const close = (result = null) => post({ type: 'close', result })
  function confirm(text) {
    const id = newId()
    return new Promise((resolve) => {
      waiting.set(id, { resolve, reject: () => resolve(false) })
      post({ type: 'confirm', id, text: String(text) })
    })
  }

  if (options.autoResize !== false && 'ResizeObserver' in window) {
    new ResizeObserver(() => resize()).observe(document.documentElement)
  }
  post({ type: 'ready' })
  return {
    context,
    api,
    token,
    resize,
    toast,
    navigate,
    refresh,
    close,
    confirm,
    refreshContext: () => post({ type: 'context' }),
  }
}

/** A packaged plugin's page is served by Desktiny itself, so Desktiny's origin is the page address's own. */
function servedOrigin() {
  try {
    const url = new URL(window.location.href)
    return url.pathname.startsWith('/workspace/v1/plugin-files/') ? url.origin : null
  } catch {
    return null
  }
}

function newId() {
  return (globalThis.crypto && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2))
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
