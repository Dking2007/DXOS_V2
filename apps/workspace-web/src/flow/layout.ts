// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors

export interface Point {
  x: number
  y: number
}
export interface LayoutNode {
  id: string
  x: number
  y: number
  width?: number
  height?: number
  /** The flow's trigger: always first, in the left-most column. */
  start?: boolean
}
export interface LayoutEdge {
  source: string
  target: string
  /** Position of the exit on its step (Duyệt above Trả lại above Từ chối); keeps branches in order. */
  order?: number
}
export interface LayoutOptions {
  nodeWidth?: number
  nodeHeight?: number
  /** Room between columns: branch tags sit to the right of a step. */
  gapX?: number
  gapY?: number
  grid?: number
}

const DEFAULTS = { nodeWidth: 250, nodeHeight: 80, gapX: 110, gapY: 48, grid: 20 }

/**
 * Left-to-right layered layout: each step goes one column after the furthest step leading to it,
 * branches stack in their exit order, and connections that go back (Trả lại, loops) are ignored
 * so they never push steps around. The result keeps the drawing where it was on the canvas.
 */
export function autoLayout(nodes: LayoutNode[], edges: LayoutEdge[], options: LayoutOptions = {}): Record<string, Point> {
  const o = { ...DEFAULTS, ...options }
  if (!nodes.length) return {}
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const out = new Map<string, LayoutEdge[]>(nodes.map((node) => [node.id, []]))
  const incoming = new Map<string, number>(nodes.map((node) => [node.id, 0]))
  for (const edge of edges) {
    if (!byId.has(edge.source) || !byId.has(edge.target) || edge.source === edge.target) continue
    out.get(edge.source)!.push(edge)
    incoming.set(edge.target, incoming.get(edge.target)! + 1)
  }
  for (const list of out.values()) list.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))

  // Roots: the trigger, then steps nothing leads to, top to bottom; then anything only reachable in a loop.
  const byPlace = (a: LayoutNode, b: LayoutNode) => Number(!!b.start) - Number(!!a.start) || a.y - b.y || a.x - b.x
  const roots = nodes.filter((node) => node.start || incoming.get(node.id) === 0).sort(byPlace)
  const rest = nodes.filter((node) => !roots.includes(node)).sort(byPlace)

  // Depth-first walk in exit order: finds the connections that go back and a natural top-to-bottom order.
  const seen = new Map<string, number>()
  const onPath = new Set<string>()
  const back = new Set<LayoutEdge>()
  function walk(id: string) {
    seen.set(id, seen.size)
    onPath.add(id)
    for (const edge of out.get(id)!) {
      if (onPath.has(edge.target)) back.add(edge)
      else if (!seen.has(edge.target)) walk(edge.target)
    }
    onPath.delete(id)
  }
  for (const node of [...roots, ...rest]) if (!seen.has(node.id)) walk(node.id)

  // Longest path over forward connections gives each step its column.
  const forward = edges.filter((edge) => out.get(edge.source)?.includes(edge) && !back.has(edge))
  const pending = new Map<string, number>(nodes.map((node) => [node.id, 0]))
  for (const edge of forward) pending.set(edge.target, pending.get(edge.target)! + 1)
  const column = new Map<string, number>(nodes.map((node) => [node.id, 0]))
  const queue = nodes.filter((node) => pending.get(node.id) === 0).map((node) => node.id)
  while (queue.length) {
    const id = queue.shift()!
    for (const edge of out.get(id)!) {
      if (back.has(edge)) continue
      column.set(edge.target, Math.max(column.get(edge.target)!, column.get(id)! + 1))
      pending.set(edge.target, pending.get(edge.target)! - 1)
      if (pending.get(edge.target) === 0) queue.push(edge.target)
    }
  }

  const parents = new Map<string, string[]>(nodes.map((node) => [node.id, []]))
  for (const edge of forward) parents.get(edge.target)!.push(edge.source)
  const height = (id: string) => byId.get(id)!.height ?? o.nodeHeight
  const center = new Map<string, number>()
  const columns: string[][] = []
  for (const node of nodes) (columns[column.get(node.id)!] ??= []).push(node.id)

  for (const ids of columns) {
    if (!ids) continue
    const wish = new Map<string, number>()
    ids.forEach((id) => {
      const from = parents.get(id)!.filter((parent) => center.has(parent))
      wish.set(id, from.length ? from.reduce((sum, parent) => sum + center.get(parent)!, 0) / from.length : NaN)
    })
    // Steps without a placed parent (roots) simply stack below each other.
    let stack = 0
    for (const id of [...ids].sort((a, b) => seen.get(a)! - seen.get(b)!))
      if (Number.isNaN(wish.get(id)!)) {
        wish.set(id, stack + height(id) / 2)
        stack += height(id) + o.gapY * 2
      }
    const ordered = [...ids].sort((a, b) => wish.get(a)! - wish.get(b)! || seen.get(a)! - seen.get(b)!)
    // Place each as close to its wish as the one above allows, then centre the column on the wishes.
    let bottom = -Infinity
    const placed = ordered.map((id) => {
      const y = Math.max(wish.get(id)!, bottom + height(id) / 2)
      bottom = y + height(id) / 2 + o.gapY
      return y
    })
    const drift = ordered.reduce((sum, id, index) => sum + (wish.get(id)! - placed[index]!), 0) / ordered.length
    ordered.forEach((id, index) => center.set(id, placed[index]! + drift))
  }

  const step = o.nodeWidth + o.gapX
  const raw = nodes.map((node) => ({
    id: node.id,
    x: column.get(node.id)! * step,
    y: center.get(node.id)! - height(node.id) / 2,
  }))
  // Keep the drawing where it was: the new top-left corner is the old one.
  const shift = {
    x: Math.min(...nodes.map((node) => node.x)) - Math.min(...raw.map((node) => node.x)),
    y: Math.min(...nodes.map((node) => node.y)) - Math.min(...raw.map((node) => node.y)),
  }
  const snap = (value: number) => Math.round(value / o.grid) * o.grid
  return Object.fromEntries(raw.map((node) => [node.id, { x: snap(node.x + shift.x), y: snap(node.y + shift.y) }]))
}

export interface Box {
  id: string
  x: number
  y: number
  width: number
  height: number
}
export type AlignMode = 'left' | 'center' | 'top' | 'middle' | 'distribute-h' | 'distribute-v'

/** Lines selected steps up, or spaces them evenly between the outermost two. */
export function alignBoxes(boxes: Box[], mode: AlignMode): Record<string, Point> {
  if (boxes.length < 2) return Object.fromEntries(boxes.map((box) => [box.id, { x: box.x, y: box.y }]))
  const result: Record<string, Point> = Object.fromEntries(boxes.map((box) => [box.id, { x: box.x, y: box.y }]))
  switch (mode) {
    case 'left': {
      const x = Math.min(...boxes.map((box) => box.x))
      for (const box of boxes) result[box.id]!.x = x
      break
    }
    case 'top': {
      const y = Math.min(...boxes.map((box) => box.y))
      for (const box of boxes) result[box.id]!.y = y
      break
    }
    case 'center': {
      const x = boxes.reduce((sum, box) => sum + box.x + box.width / 2, 0) / boxes.length
      for (const box of boxes) result[box.id]!.x = Math.round(x - box.width / 2)
      break
    }
    case 'middle': {
      const y = boxes.reduce((sum, box) => sum + box.y + box.height / 2, 0) / boxes.length
      for (const box of boxes) result[box.id]!.y = Math.round(y - box.height / 2)
      break
    }
    case 'distribute-h':
    case 'distribute-v': {
      const horizontal = mode === 'distribute-h'
      const start = (box: Box) => (horizontal ? box.x : box.y)
      const size = (box: Box) => (horizontal ? box.width : box.height)
      const sorted = [...boxes].sort((a, b) => start(a) - start(b))
      const first = sorted[0]!
      const last = sorted.reduce((far, box) => (start(box) + size(box) > start(far) + size(far) ? box : far))
      const span = start(last) + size(last) - start(first)
      const used = sorted.reduce((sum, box) => sum + size(box), 0)
      const gap = Math.max(0, (span - used) / (sorted.length - 1))
      let cursor = start(first)
      for (const box of sorted) {
        result[box.id]![horizontal ? 'x' : 'y'] = Math.round(cursor)
        cursor += size(box) + gap
      }
      break
    }
  }
  return result
}

/**
 * Where a step inserted on a connection goes, and which steps after it move right to make room.
 * Only steps downstream of the connection and not left of its target move, so loops stay put.
 */
export function makeRoom(
  nodes: (Point & { id: string })[],
  edges: { source: string; target: string }[],
  from: { id: string; x: number; y: number },
  to: { id: string; x: number; y: number },
  step = 360,
): { at: Point; moved: Record<string, Point> } {
  const positions = new Map(nodes.map((node) => [node.id, node]))
  if (to.x <= from.x) {
    // The connection runs backwards: put the new step below, between the two.
    return { at: { x: Math.round((from.x + to.x) / 2), y: Math.max(from.y, to.y) + 160 }, moved: {} }
  }
  const at = { x: from.x + step, y: Math.round((from.y + to.y) / 2) }
  const need = from.x + step * 2 - to.x
  if (need <= 0) return { at: { x: Math.round((from.x + to.x) / 2), y: at.y }, moved: {} }
  const moved: Record<string, Point> = {}
  const queue = [to.id]
  while (queue.length) {
    const id = queue.shift()!
    const node = positions.get(id)
    if (!node || moved[id] || id === from.id || node.x < to.x) continue
    moved[id] = { x: node.x + need, y: node.y }
    for (const edge of edges) if (edge.source === id) queue.push(edge.target)
  }
  return { at, moved }
}

/**
 * "Vừa màn hình" shows the whole flow, never magnified past 100%. On a wide screen names stay readable;
 * on a phone the button gives the overview even if it is small (opening uses `narrowViewport` instead).
 */
export const FIT_VIEW = {
  padding: 0.08,
  get minZoom() {
    return window.innerWidth < NARROW_CANVAS ? 0.2 : 0.5
  },
  maxZoom: 1,
}

/** A step's place and size on the canvas, in flow coordinates. */
export type Area = Omit<Box, 'id'>
export interface Viewport {
  x: number
  y: number
  zoom: number
}
/** A canvas narrower than this is a phone (or a squeezed pane): it opens on readable steps, not a thumbnail. */
export const NARROW_CANVAS = 640
/** Smallest zoom at which a step's name (15px) still reads on a phone: about 11px. */
export const READABLE_ZOOM = 0.75

/**
 * Where a narrow canvas opens. A flow that fits at a readable size is shown whole and centred, never
 * past 100%. A longer one stays at the readable size and starts at the trigger on the left edge, so it
 * reads from its first step and the rest is one swipe away instead of a pinch.
 */
export function narrowViewport(
  boxes: Area[],
  pane: { width: number; height: number },
  options: { start?: Area; padding?: number; readable?: number; maxZoom?: number } = {},
): Viewport {
  const pad = options.padding ?? 16
  const maxZoom = options.maxZoom ?? 1
  const readable = Math.min(options.readable ?? READABLE_ZOOM, maxZoom)
  if (!boxes.length || pane.width <= 0 || pane.height <= 0) return { x: 0, y: 0, zoom: 1 }
  const left = Math.min(...boxes.map((b) => b.x))
  const top = Math.min(...boxes.map((b) => b.y))
  const right = Math.max(...boxes.map((b) => b.x + b.width))
  const bottom = Math.max(...boxes.map((b) => b.y + b.height))
  const width = Math.max(right - left, 1)
  const height = Math.max(bottom - top, 1)
  const roomX = Math.max(pane.width - pad * 2, 1)
  const roomY = Math.max(pane.height - pad * 2, 1)
  const fit = Math.min(roomX / width, roomY / height, maxZoom)
  const centre = (size: number, room: number, from: number, zoom: number) => (room - size * zoom) / 2 - from * zoom
  if (fit >= readable) {
    return { x: centre(width, pane.width, left, fit), y: centre(height, pane.height, top, fit), zoom: fit }
  }
  const zoom = readable
  const x = pad - left * zoom
  if (height * zoom <= roomY) return { x, y: centre(height, pane.height, top, zoom), zoom }
  // Taller than the pane as well: the trigger's row in the middle, without empty space above or below the flow.
  const anchor = options.start ? options.start.y + options.start.height / 2 : top + height / 2
  const y = Math.max(Math.min(pane.height / 2 - anchor * zoom, pad - top * zoom), pane.height - pad - bottom * zoom)
  return { x, y, zoom }
}
