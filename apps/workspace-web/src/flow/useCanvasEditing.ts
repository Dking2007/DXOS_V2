// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { Edge, GraphNode, Node, VueFlowStore } from '@vue-flow/core'
import { copyNodes, parseClip, pasteClip, serializeClip } from './clipboard'
import type { FlowClip, PasteResult } from './clipboard'
import { heldWhile } from './held'
import { UndoHistory } from './history'
import { FIT_VIEW, NARROW_CANVAS, alignBoxes, autoLayout, narrowViewport } from './layout'
import type { AlignMode, Point } from './layout'
import { outputs, toApi, toCanvas } from './nodes'
import type { ApiGraph, FlowNodeData, NodeKind } from './nodes'

/** Copied steps live for the whole browser tab, so they can be pasted into another flow. */
let memory: FlowClip | null = null

export interface CanvasEditingOptions {
  nodes: Ref<Node<FlowNodeData>[]>
  edges: Ref<Edge[]>
  flow: VueFlowStore
  newId: (kind: NodeKind) => string
  maxNodes: () => number
  /** The step open in the inspector; stands in for the selection when nothing is selected. */
  current: () => string | null
  /** Opens a step in the inspector, or closes it. */
  open: (id: string | null) => void
  /** Short message on the canvas; `undoable` adds a "Hoàn tác" button. */
  notify: (text: string, undoable?: boolean) => void
  /** Runs before any edit, e.g. to clear a painted run. */
  beforeChange?: () => void
}

const SIZE = { width: 250, height: 80 }
function box(node: GraphNode) {
  return {
    id: node.id,
    x: node.position.x,
    y: node.position.y,
    width: node.dimensions?.width || SIZE.width,
    height: node.dimensions?.height || SIZE.height,
  }
}

/** Clipboard, undo/redo, selection, alignment and tidy-up for the flow designer. */
export function useCanvasEditing(o: CanvasEditingOptions) {
  const { flow } = o
  const graph = (): ApiGraph => toApi(o.nodes.value, o.edges.value)
  /** The graph as it is right now; for explicit reads (undo, reset), never held. */
  const json = () => JSON.stringify(graph())
  const dragging = ref(false)
  /**
   * The graph as JSON for whatever watches it (undo, "unsaved", live validation). A drag moves
   * steps on every pointer move; the value holds still until the drag ends instead of
   * re-serialising the whole graph each frame.
   */
  const graphJson = heldWhile(dragging, json)

  // ---- Undo / redo: a snapshot after every settled change ----
  const history = new UndoHistory<string>(50)
  const version = ref(0)
  let timer: ReturnType<typeof setTimeout> | undefined
  function commit() {
    clearTimeout(timer)
    if (history.record(json())) version.value += 1
  }
  // Typing in the inspector or nudging settles into one step after a short pause.
  watch(graphJson, () => {
    if (dragging.value) return
    clearTimeout(timer)
    timer = setTimeout(commit, 400)
  })
  const startDrag = () => (dragging.value = true)
  const stopDrag = () => {
    dragging.value = false
    commit()
  }
  flow.onNodeDragStart(startDrag)
  flow.onSelectionDragStart(startDrag)
  flow.onNodeDragStop(stopDrag)
  flow.onSelectionDragStop(stopDrag)
  onBeforeUnmount(() => clearTimeout(timer))

  /** Starts the history over from what is on the canvas now (a flow just opened). */
  function resetHistory() {
    clearTimeout(timer)
    history.reset(json())
    version.value += 1
  }
  function restore(state: string | undefined) {
    if (state === undefined) return false
    o.beforeChange?.()
    const canvas = toCanvas(JSON.parse(state) as ApiGraph)
    o.nodes.value = canvas.nodes
    o.edges.value = canvas.edges
    // The restored canvas is the present state, even if ids or rounding differ slightly from the snapshot.
    history.replace(json())
    void nextTick(() => {
      clearTimeout(timer)
      history.replace(json())
    })
    const open = o.current()
    if (open && !canvas.nodes.some((node) => node.id === open)) o.open(null)
    version.value += 1
    return true
  }
  function undo() {
    commit()
    if (!restore(history.undo())) o.notify('Không còn thao tác nào để hoàn tác.')
  }
  function redo() {
    commit()
    if (!restore(history.redo())) o.notify('Không còn thao tác nào để làm lại.')
  }
  const canUndo = computed(() => version.value >= 0 && history.canUndo)
  const canRedo = computed(() => version.value >= 0 && history.canRedo)

  // ---- Selection ----
  const selectedNodes = computed(() => flow.getSelectedNodes.value)
  function selectedIds(): string[] {
    const ids = selectedNodes.value.map((node) => node.id)
    const open = o.current()
    return ids.length ? ids : open ? [open] : []
  }
  function selectOnly(ids: string[]) {
    void nextTick(() => {
      flow.removeSelectedElements()
      const found = ids.map((id) => flow.findNode(id)).filter((node): node is GraphNode => !!node)
      if (found.length) flow.addSelectedNodes(found)
    })
  }
  function selectAll() {
    flow.addSelectedNodes(flow.getNodes.value)
    o.open(null)
  }
  function clearSelection() {
    flow.removeSelectedElements()
  }

  // ---- Clipboard ----
  let pasteRound = 0
  const hasClip = ref(!!memory)
  function copy(ids = selectedIds(), quiet = false): FlowClip | null {
    if (!ids.length) {
      o.notify('Chọn bước cần sao chép trước.')
      return null
    }
    const { clip, skipped } = copyNodes(graph(), ids)
    if (!clip.nodes.length) {
      o.notify('Không sao chép được bước kích hoạt: mỗi luồng chỉ có một.')
      return null
    }
    memory = clip
    hasClip.value = true
    pasteRound = 0
    try {
      // Also on the system clipboard, so another tab can paste; refusals are harmless.
      void navigator.clipboard?.writeText(serializeClip(clip)).catch(() => undefined)
    } catch {
      // No clipboard access (insecure page, old browser): the in-tab copy still works.
    }
    if (!quiet)
      o.notify(`Đã sao chép ${clip.nodes.length} bước${skipped ? ' (bỏ qua bước kích hoạt)' : ''}.`)
    return clip
  }
  function cut() {
    const ids = selectedIds()
    const clip = copy(ids, true)
    if (!clip) return
    remove(ids, `Đã cắt ${clip.nodes.length} bước. Bấm Ctrl+V để dán.`)
  }
  function insert(result: PasteResult, verb: string) {
    if (!result.nodes.length) {
      o.notify(result.triggers ? 'Không dán được bước kích hoạt: mỗi luồng chỉ có một.' : 'Luồng đã đạt số bước tối đa.')
      return
    }
    o.beforeChange?.()
    const canvas = toCanvas({ nodes: result.nodes, edges: result.edges })
    o.nodes.value = [...o.nodes.value, ...canvas.nodes]
    o.edges.value = [...o.edges.value, ...canvas.edges]
    selectOnly(result.nodes.map((node) => node.id))
    o.open(result.nodes.length === 1 ? result.nodes[0]!.id : null)
    const notes = [
      result.triggers ? 'bỏ qua bước kích hoạt' : '',
      result.overflow ? `bỏ ${result.overflow} bước vì luồng đã đủ số bước tối đa` : '',
    ].filter(Boolean)
    o.notify(`${verb} ${result.nodes.length} bước${notes.length ? ` (${notes.join('; ')})` : ''}.`, true)
  }
  /** Pastes copied steps; `at` is the top-left corner in flow coordinates, else they land beside the originals. */
  function paste(at?: Point | null, clip: FlowClip | null = memory) {
    if (!clip) {
      o.notify('Chưa có bước nào được sao chép. Chọn bước rồi bấm Ctrl+C.')
      return
    }
    const room = o.maxNodes() - o.nodes.value.length
    if (room <= 0) {
      o.notify('Luồng đã đạt số bước tối đa.')
      return
    }
    pasteRound += 1
    const result = pasteClip(clip, {
      existing: graph().nodes,
      newId: o.newId,
      room,
      at: at ?? undefined,
      offset: { x: 40 * pasteRound, y: 40 * pasteRound },
    })
    insert(result, 'Đã dán')
  }
  /** Clipboard text from another tab; null when it is not copied steps. */
  function pasteText(text: string, at?: Point | null) {
    const clip = parseClip(text)
    if (!clip) return false
    if (!memory || serializeClip(memory) !== serializeClip(clip)) {
      memory = clip
      hasClip.value = true
      pasteRound = 0
    }
    paste(at, clip)
    return true
  }
  /** The system clipboard, for "Dán ở đây" in the menu where no paste event comes. */
  async function readClipboard(): Promise<FlowClip | null> {
    try {
      return parseClip(await navigator.clipboard.readText())
    } catch {
      return null
    }
  }
  function duplicate() {
    const ids = selectedIds()
    if (!ids.length) {
      o.notify('Chọn bước cần nhân bản trước.')
      return
    }
    const { clip } = copyNodes(graph(), ids)
    if (!clip.nodes.length) {
      o.notify('Không nhân bản được bước kích hoạt: mỗi luồng chỉ có một.')
      return
    }
    const boxes = clip.nodes.map((node) => flow.findNode(node.id)).filter((node): node is GraphNode => !!node).map(box)
    const left = Math.min(...boxes.map((item) => item.x))
    const bottom = Math.max(...boxes.map((item) => item.y + item.height))
    const room = o.maxNodes() - o.nodes.value.length
    insert(
      pasteClip(clip, { existing: graph().nodes, newId: o.newId, room, at: { x: left + 40, y: bottom + 40 } }),
      'Đã nhân bản',
    )
  }

  // ---- Delete and disconnect ----
  function remove(ids = selectedIds(), message?: string) {
    const kinds = new Map(o.nodes.value.map((node) => [node.id, node.data?.kind]))
    const gone = new Set(ids.filter((id) => kinds.has(id) && kinds.get(id) !== 'trigger'))
    const lines = new Set(flow.getSelectedEdges.value.map((edge) => edge.id))
    if (!gone.size && !lines.size) {
      if (ids.length) o.notify('Không xóa được bước kích hoạt: mỗi luồng cần đúng một.')
      return
    }
    o.beforeChange?.()
    o.nodes.value = o.nodes.value.filter((node) => !gone.has(node.id))
    o.edges.value = o.edges.value.filter(
      (edge) => !lines.has(edge.id) && !gone.has(edge.source) && !gone.has(edge.target),
    )
    const open = o.current()
    if (open && gone.has(open)) o.open(null)
    const parts = [gone.size ? `${gone.size} bước` : '', lines.size ? `${lines.size} đường nối` : ''].filter(Boolean)
    o.notify(message ?? `Đã xóa ${parts.join(' và ')}.`, true)
  }
  function disconnect(ids = selectedIds()) {
    const set = new Set(ids)
    const before = o.edges.value.length
    o.beforeChange?.()
    o.edges.value = o.edges.value.filter((edge) => !set.has(edge.source) && !set.has(edge.target))
    const count = before - o.edges.value.length
    o.notify(count ? `Đã ngắt ${count} đường nối.` : 'Bước này chưa nối với bước nào.', count > 0)
  }

  // ---- Moving ----
  function move(positions: Record<string, Point>) {
    for (const [id, position] of Object.entries(positions)) flow.updateNode(id, { position: { ...position } })
  }
  function nudge(dx: number, dy: number) {
    const ids = selectedIds()
    if (!ids.length) return false
    move(
      Object.fromEntries(
        ids
          .map((id) => flow.findNode(id))
          .filter((node): node is GraphNode => !!node)
          .map((node) => [node.id, { x: node.position.x + dx, y: node.position.y + dy }]),
      ),
    )
    return true
  }
  function align(mode: AlignMode) {
    move(alignBoxes(selectedNodes.value.map(box), mode))
  }
  function tidy() {
    const kinds = new Map(o.nodes.value.map((node) => [node.id, node.data!]))
    const positions = autoLayout(
      flow.getNodes.value.map((node) => ({ ...box(node), start: kinds.get(node.id)?.kind === 'trigger' })),
      o.edges.value.map((edge) => {
        const data = kinds.get(edge.source)
        return {
          source: edge.source,
          target: edge.target,
          order: data ? outputs(data.kind, data.config).indexOf(edge.sourceHandle as never) : 0,
        }
      }),
    )
    o.beforeChange?.()
    move(positions)
    void nextTick(() => fitOpening(300))
    o.notify('Đã sắp xếp lại các bước.', true)
  }
  /**
   * The view a flow opens on (and returns to after tidying). A wide canvas shows the whole flow; a phone
   * shows it at a readable size from the trigger, instead of shrinking a long flow to a thumbnail.
   */
  function fitOpening(duration = 0) {
    const pane = flow.dimensions.value
    const shown = flow.getNodes.value.filter((node) => !node.hidden)
    if (!shown.length || !pane.width || pane.width >= NARROW_CANVAS) return flow.fitView({ ...FIT_VIEW, duration })
    const start = shown.find((node) => o.nodes.value.find((n) => n.id === node.id)?.data?.kind === 'trigger')
    return flow.setViewport(narrowViewport(shown.map(box), pane, { start: start && box(start) }), { duration })
  }

  return {
    /** The graph as JSON, held still during a drag; compare against it instead of serialising again. */
    graphJson,
    history: { undo, redo, canUndo, canRedo, reset: resetHistory, commit },
    selectedNodes,
    selectedIds,
    selectOnly,
    selectAll,
    clearSelection,
    hasClip,
    copy,
    cut,
    paste,
    pasteText,
    readClipboard,
    duplicate,
    remove,
    disconnect,
    nudge,
    align,
    tidy,
    fitOpening,
  }
}
