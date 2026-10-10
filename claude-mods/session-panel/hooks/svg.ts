// The desktop drawings: pure functions from plain data to SVG strings, so a
// browser can preview them and tests can read them without the engine.
// Colors that must follow the theme are CSS classes with a dark variant.

import type { AgentStatus } from '../types'

const FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',sans-serif"

export const TONE = {
  ok: '#3b9c5f',
  bad: '#d0453f',
  run: '#d9a23b',
  bg: '#6f86d6',
  plain: '#8a8580',
} as const
export type Tone = keyof typeof TONE

const CSS = `
.t{fill:#1f1f1f}.s{fill:#6b6b68}.g{stroke:#000;stroke-opacity:.07}.bg{fill:#000;fill-opacity:.035}
@media (prefers-color-scheme: dark){.t{fill:#ececec}.s{fill:#a8a8a4}.g{stroke:#fff;stroke-opacity:.09}.bg{fill:#fff;fill-opacity:.05}}
.pulse{animation:pulse 1s ease-in-out infinite}@keyframes pulse{50%{opacity:.4}}
@media (prefers-reduced-motion: reduce){*{animation:none!important}}`

export const xml = (s: string): string =>
  s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] ?? c)

// Rough advance of system UI text, in em; good enough to cut a line to its slot.
const charEm = (ch: string): number =>
  /[\s.,:;'|!il1()[\]]/.test(ch) ? 0.3 : /[A-Z@%mw]/.test(ch) ? 0.72 : 0.56

const textWidth = (s: string, size: number): number => [...s].reduce((w, ch) => w + charEm(ch) * size, 0)

function fit(s: string, size: number, maxWidth: number): string {
  if (textWidth(s, size) <= maxWidth) return s
  let out = ''
  for (const ch of s) {
    if (textWidth(out + ch + '…', size) > maxWidth) break
    out += ch
  }
  return out + '…'
}

const text = (x: number, y: number, size: number, body: string, attrs = ''): string =>
  `<text x="${x}" y="${y}" font-family="${FONT}" font-size="${size}" ${attrs}>${xml(body)}</text>`

const svg = (width: number, height: number, body: string, extraCss = ''): string =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
  `<style>${CSS}${extraCss}</style>${body}</svg>`

/** A stable hue per agent type, so the same role reads the same everywhere. */
function hueOf(type: string): number {
  return [...type].reduce((h, ch) => (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0, 7) % 360
}

/**
 * An agent type's color, as hex so text on every surface takes it: the card's
 * edge, its timeline lane and its row above the prompt all draw in it.
 */
export function agentColor(type: string): string {
  const h = hueOf(type)
  const s = 0.68
  const l = 0.54
  const channel = (n: number) => {
    const k = (n + h / 30) % 12
    const v = l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(k - 3, 9 - k, 1))
    return Math.round(v * 255).toString(16).padStart(2, '0')
  }
  return `#${channel(0)}${channel(8)}${channel(4)}`
}

export type Drawing = { source: string; height: number }

// ── Stat tiles ──────────────────────────────────────────────────────────────

export type Tile = { label: string; value: string; detail: string; tone: Tone }

const TILE_HEIGHT = 68
const TILE_GAP = 8

export function tilesSvg(tiles: readonly Tile[], width: number): Drawing {
  const columns = width >= 520 ? tiles.length : 2
  const rows = Math.ceil(tiles.length / columns)
  const w = (width - TILE_GAP * (columns - 1)) / columns
  const height = rows * TILE_HEIGHT + (rows - 1) * TILE_GAP
  const body = tiles
    .map((tile, i) => {
      const x = (i % columns) * (w + TILE_GAP)
      const y = Math.floor(i / columns) * (TILE_HEIGHT + TILE_GAP)
      const tone = TONE[tile.tone]
      const detailAttrs = tile.tone === 'plain' ? 'class="s"' : `fill="${tone}"`
      return (
        `<g transform="translate(${x},${y})">` +
        `<rect class="bg" width="${w}" height="${TILE_HEIGHT}" rx="10"/>` +
        text(12, 21, 11, fit(tile.label, 11, w - 24), 'class="s"') +
        text(12, 45, 20, fit(tile.value, 20, w - 24), 'class="t" font-weight="600" font-variant-numeric="tabular-nums"') +
        text(12, 60, 11, fit(tile.detail, 11, w - 24), detailAttrs) +
        `</g>`
      )
    })
    .join('')
  return { source: svg(width, height, body), height }
}

// ── Timeline ────────────────────────────────────────────────────────────────
// One strip per lane, each its own SVG, so the pane can set a real Button
// beside it as the lane's label. Every strip and the axis share one x scale:
// the same width, from and to give the same positions.

export type Span = {
  start: number
  /** Absent while it runs: the span reaches the timeline's end and pulses. */
  end?: number
  color: string
  isFailed?: boolean
}

export type Lane = {
  color: string
  /** Bars: shell commands, a subagent's whole run. */
  spans: readonly Span[]
  /** Ticks: single tool calls, drawn over the bars. */
  ticks: readonly Span[]
}

export const AXIS_HEIGHT = 18
export const LANE_HEIGHT = 24
const PLOT_LEFT = 16
const PLOT_RIGHT = 8

function axisStep(spanMs: number): number {
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600].map(s => s * 1000)
  return steps.find(step => spanMs / step <= 6) ?? 7200_000
}

function scale(from: number, to: number, width: number) {
  const spanMs = Math.max(1000, to - from)
  const right = width - PLOT_RIGHT
  const x = (t: number) => PLOT_LEFT + ((Math.min(Math.max(t, from), to) - from) / spanMs) * (right - PLOT_LEFT)
  const step = axisStep(spanMs)
  const grid: number[] = []
  for (let t = 0; t <= spanMs; t += step) grid.push(t)
  return { x, step, grid, spanMs }
}

export function axisSvg(from: number, to: number, width: number): string {
  const { x, step, grid } = scale(from, to, width)
  const labels = grid.map(t => {
    const minutes = Math.floor(t / 60_000)
    const label = step >= 60_000 ? `${minutes}m` : `${minutes}:${String(Math.floor((t % 60_000) / 1000)).padStart(2, '0')}`
    return text(Number(x(from + t).toFixed(1)), 12, 10, label, 'class="s" text-anchor="middle" font-variant-numeric="tabular-nums"')
  })
  return svg(width, AXIS_HEIGHT, labels.join(''))
}

export function laneSvg(lane: Lane, from: number, to: number, width: number, isStriped: boolean): string {
  const { x, grid } = scale(from, to, width)
  const mid = LANE_HEIGHT / 2
  const stripe = isStriped ? `<rect class="bg" width="${width}" height="${LANE_HEIGHT}" rx="4" opacity=".6"/>` : ''
  const lines = grid
    .map(t => `<line class="g" x1="${x(from + t).toFixed(1)}" x2="${x(from + t).toFixed(1)}" y1="0" y2="${LANE_HEIGHT}"/>`)
    .join('')
  const dot = `<circle cx="7" cy="${mid}" r="2.5" fill="${lane.color}" fill-opacity=".8"/>`
  const bars = lane.spans
    .map(span => {
      const x1 = x(span.start)
      const w = Math.max(3, x(span.end ?? to) - x1)
      const fill = span.isFailed ? TONE.bad : span.color
      const cls = span.end === undefined ? ' class="pulse"' : ''
      return `<rect${cls} x="${x1.toFixed(1)}" y="${mid - 6}" width="${w.toFixed(1)}" height="12" rx="3" fill="${fill}" fill-opacity="${span.isFailed ? 0.55 : 0.2}" stroke="${fill}" stroke-opacity=".35"/>`
    })
    .join('')
  const ticks = lane.ticks
    .map(tick => `<rect x="${(x(tick.start) - 1).toFixed(1)}" y="${mid - 5}" width="2" height="8" rx="1" fill="${tick.isFailed ? TONE.bad : tick.color}" fill-opacity="${tick.isFailed ? 0.9 : 0.55}"/>`)
    .join('')
  return svg(width, LANE_HEIGHT, stripe + lines + dot + bars + ticks)
}

// ── Agent card ──────────────────────────────────────────────────────────────

export type AgentCard = {
  width: number
  /** The agent type: its color and the hue of its title. */
  type: string
  status: AgentStatus
  /** Nesting under the agent that spawned it, as a left indent. */
  depth: number
  title: string
  clock: string
  description: string
  /** Model, tool calls, tokens. */
  meta: string
  /** What it does now, or the first line of its answer. */
  line: string
}

export const AGENT_CARD_HEIGHT = 84

const PILL: Record<AgentStatus, { label: string; tone: Tone }> = {
  running: { label: 'running', tone: 'run' },
  done: { label: 'done', tone: 'ok' },
  stopped: { label: 'stopped', tone: 'plain' },
  failed: { label: 'failed', tone: 'bad' },
}

export function agentCardSvg(c: AgentCard): string {
  const indent = Math.min(c.depth, 4) * 18
  const W = c.width - indent
  const H = AGENT_CARD_HEIGHT - 6
  const hue = hueOf(c.type)
  const color = agentColor(c.type)
  const isRunning = c.status === 'running'
  const pill = PILL[c.status]
  const pillText = c.clock ? `${pill.label} · ${c.clock}` : pill.label
  const pillWidth = textWidth(pillText, 11) + 18
  const textX = 20
  const textMax = W - textX - 14
  const lineX = textX + (isRunning ? 12 : 0)

  // Names carry the hue, so cards drawn into one document never share a style.
  const n = `a${hue}`
  const css =
    `.c${n}{fill:hsl(${hue},45%,36%)}@media (prefers-color-scheme: dark){.c${n}{fill:hsl(${hue},55%,74%)}}`

  const body =
    `<g transform="translate(${indent},0)">` +
    `<defs><clipPath id="card${n}"><rect width="${W}" height="${H}" rx="10"/></clipPath></defs>` +
    (indent > 0 ? `<path d="M-10 0 V${H / 2} H-2" fill="none" stroke="${color}" stroke-opacity=".45" stroke-width="1.5"/>` : '') +
    `<g clip-path="url(#card${n})">` +
    `<rect class="bg" width="${W}" height="${H}"/>` +
    `<rect width="3" height="${H}" fill="${color}" fill-opacity="${isRunning ? 0.9 : 0.4}"/>` +
    `</g>` +
    text(textX, 21, 13, fit(c.title, 13, textMax - pillWidth - 8), `class="c${n}" font-weight="600"`) +
    text(W - 12 - pillWidth / 2, 21, 11, pillText, `text-anchor="middle" ${pill.tone === 'bad' || pill.tone === 'run' ? `fill="${TONE[pill.tone]}"` : 'class="s"'} font-variant-numeric="tabular-nums"`) +
    text(textX, 40, 12.5, fit(c.description, 12.5, textMax), 'class="t"') +
    text(textX, 56, 11, fit(c.meta, 11, textMax), 'class="s" font-variant-numeric="tabular-nums"') +
    (isRunning ? `<circle class="pulse" cx="${textX + 4}" cy="68" r="3.5" fill="${color}"/>` : '') +
    text(lineX, 72, 11, fit(c.line, 11, textMax - (lineX - textX)), c.status === 'failed' ? `fill="${TONE.bad}"` : 'class="s"') +
    `</g>`

  return svg(c.width, AGENT_CARD_HEIGHT, body, css)
}
