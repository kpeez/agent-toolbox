// The desktop drawing: one SVG card per agent, so the desktop never wraps a
// row's parts onto separate lines. The sprite is the same pixel Clawd as the
// terminal's, built from rects at 3.5 CSS px a pixel, and animated by CSS.
//
// The pane redraws once a second while an agent runs, and a redraw restarts
// the animations, so every period divides a second; a blink is the redraw's
// choice instead of a timer of its own.

import type { AgentStatus } from '../types'

export const CARD_HEIGHT = 66

const CLAY = '#d97757'
const ASH = '#8a8580'
const INK = '#1f1e1d'
const OK = '#3b9c5f'
const BAD = '#d0453f'
const FONT = "-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',sans-serif"
const SCALE = 3.5
const SPRITE_X = 14
const TEXT_X = 104

export type Card = {
  width: number
  hue: number
  status: AgentStatus | 'idle'
  label: string
  clock: string
  description: string
  line: string
  /** Shifts the walk cycle, so agents step out of time with each other. */
  phase: number
  isBlinking: boolean
}

const xml = (s: string): string =>
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

const px = (x: number, y: number, w: number, h: number, fill: string, cls = ''): string =>
  `<rect${cls ? ` class="${cls}"` : ''} x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}"/>`

const CSS = `
.t{fill:#1f1f1f}.s{fill:#6b6b68}
@media (prefers-color-scheme: dark){.t{fill:#ececec}.s{fill:#a8a8a4}}
.fb{transform-box:fill-box}
.bob{animation:bob .25s ease-in-out infinite}
@keyframes bob{50%{transform:translateY(-1px)}}
.sh{transform-origin:center;animation:sh .25s ease-in-out infinite}
@keyframes sh{50%{transform:scaleX(.8);opacity:.1}}
.la{animation:la .25s steps(1) infinite}.lb{animation:la .25s steps(1) infinite -.125s}
@keyframes la{50%{opacity:0}}
.al{transform-origin:100% 50%;animation:al .5s ease-in-out infinite}
.ar{transform-origin:0 50%;animation:ar .5s ease-in-out infinite}
@keyframes al{50%{transform:rotate(-40deg)}}@keyframes ar{50%{transform:rotate(40deg)}}
.hat{transform-origin:50% 100%;animation:hat .5s ease-in-out infinite}
@keyframes hat{25%{transform:rotate(-10deg)}75%{transform:rotate(10deg)}}
.lid{opacity:0;animation:lid 1s steps(1) infinite}
@keyframes lid{0%{opacity:0}80%{opacity:1}92%{opacity:0}}
.sp{transform-origin:center;animation:sp 1s ease-in-out infinite;opacity:0}
.sp1{animation-delay:.33s}.sp2{animation-delay:.66s}
@keyframes sp{0%{opacity:0;transform:scale(.4)}25%{opacity:1;transform:scale(1.1)}60%,100%{opacity:0;transform:scale(.4)}}
.br{transform-origin:50% 100%;animation:br 1s ease-in-out infinite}
@keyframes br{50%{transform:scaleY(.95)}}
.dot{transform-origin:center;animation:dot 1s ease-in-out infinite}
@keyframes dot{50%{transform:scale(.55);opacity:.5}}
.shim{animation:shim 1s linear infinite}
.z{opacity:0;animation:z 3s ease-out infinite}.z1{animation-delay:1s}.z2{animation-delay:2s}
@keyframes z{0%{opacity:0;transform:translate(0,0)}20%{opacity:1}100%{opacity:0;transform:translate(3px,-6px)}}
@media (prefers-reduced-motion: reduce){*{animation:none!important}.lid,.sp,.z{opacity:0}}
`

// The Clawd in sprite pixels (18 by 6, as the terminal draws it), wearing a
// party hat in the agent's color, with what its status adds: sparkles while
// it works, a badge once it ends, z's while the pane waits.
function clawd(c: Card, color: string): string {
  const isRunning = c.status === 'running'
  const body = c.status === 'stopped' || c.status === 'failed' ? ASH : CLAY
  const walk = (cls: string) => (isRunning ? cls : '')

  const legsA = [4, 6, 11, 13].map(x => px(x, 4, 1, 1, body)).join('')
  const legsB = [5, 7, 10, 12].map(x => px(x, 4, 1, 1, body)).join('')
  const legs = isRunning
    ? `<g class="la">${legsA}</g><g class="lb">${legsB}</g>`
    : legsA

  const hat =
    `<g class="${walk('hat fb')}">` +
    `<path d="M6.5 0 L9 -4.2 L11.5 0 Z" fill="${color}"/>` +
    `<path d="M7.6 -1.8 L10.4 -1.8 L10.9 -0.9 L7.1 -0.9 Z" fill="#fff" opacity=".7"/>` +
    `<circle cx="9" cy="-4.4" r=".8" fill="#fff"/><circle cx="9" cy="-4.4" r=".45" fill="${color}"/></g>`

  const eyes =
    c.status === 'done' || c.status === 'idle'
      ? `<path d="M4.5 1.7 L5.5 1 L6.5 1.7 M11.5 1.7 L12.5 1 L13.5 1.7" fill="none" stroke="${INK}" stroke-width=".45" stroke-linecap="round" stroke-linejoin="round"/>`
      : c.status === 'failed'
        ? `<path d="M4.6 .6 L6.4 2 M6.4 .6 L4.6 2 M11.6 .6 L13.4 2 M13.4 .6 L11.6 2" stroke="${INK}" stroke-width=".45" stroke-linecap="round"/>`
        : c.status === 'stopped'
          ? `<path d="M4.6 1.4 L6.4 1.4 M11.6 1.4 L13.4 1.4" stroke="${INK}" stroke-width=".45" stroke-linecap="round"/>`
          : px(5, 1, 1, 1, INK) + px(12, 1, 1, 1, INK) +
            (c.isBlinking ? px(5, 1, 1, 1, body, 'lid') + px(12, 1, 1, 1, body, 'lid') : '')

  const arms = isRunning
    ? `<g class="al fb">${px(1, 2, 2, 1, body)}</g><g class="ar fb">${px(15, 2, 2, 1, body)}</g>`
    : px(1, 2, 2, 1, body) + px(15, 2, 2, 1, body)

  const sparkle = (x: number, y: number, cls: string) =>
    `<path class="sp ${cls} fb" d="M${x} ${y - 1.1} L${x + 0.3} ${y - 0.3} L${x + 1.1} ${y} L${x + 0.3} ${y + 0.3} L${x} ${y + 1.1} L${x - 0.3} ${y + 0.3} L${x - 1.1} ${y} L${x - 0.3} ${y - 0.3} Z" fill="${color}"/>`

  const extra = isRunning
    ? sparkle(18.6, -2.4, 'sp0') + sparkle(20.4, 0.2, 'sp1') + sparkle(17.4, 0.9, 'sp2')
    : c.status === 'done'
      ? `<circle cx="17.2" cy="-1.6" r="1.9" fill="${OK}"/><path d="M16.3 -1.6 L17 -0.9 L18.2 -2.3" fill="none" stroke="#fff" stroke-width=".45" stroke-linecap="round" stroke-linejoin="round"/>`
      : c.status === 'failed'
        ? `<circle cx="17.2" cy="-1.6" r="1.9" fill="${BAD}"/><path d="M16.5 -2.3 L17.9 -0.9 M17.9 -2.3 L16.5 -0.9" stroke="#fff" stroke-width=".45" stroke-linecap="round"/>`
        : c.status === 'idle'
          ? ['z0', 'z1', 'z2'].map(z => `<text class="z ${z} s" x="16" y="-1" font-family="${FONT}" font-size="2.6" font-weight="700">z</text>`).join('')
          : ''

  return (
    `<g transform="translate(${SPRITE_X},${CARD_HEIGHT / 2 - 4}) scale(${SCALE})">` +
    `<ellipse class="${walk('sh fb')}" cx="9" cy="5.3" rx="6.5" ry=".6" fill="#000" opacity=".16"/>` +
    `<g shape-rendering="crispEdges">${legs}</g>` +
    `<g class="${isRunning ? 'bob' : c.status === 'idle' || c.status === 'done' ? 'br fb' : ''}">` +
    `<g shape-rendering="crispEdges">${px(3, 0, 12, 4, body)}${arms}</g>${eyes}${hat}</g>` +
    extra +
    `</g>`
  )
}

export function cardSvg(c: Card): string {
  const W = c.width
  const H = CARD_HEIGHT - 6
  const color = `hsl(${c.hue},72%,56%)`
  const isRunning = c.status === 'running'
  const delay = `-${(c.phase % 4) * 0.125}s`
  const textWidthMax = W - TEXT_X - 14
  const clockWidth = textWidth(c.clock, 11) + 10
  const lineFill = c.status === 'failed' ? ` fill="${BAD}"` : ' class="s"'
  const lineX = TEXT_X + (isRunning ? 10 : 0)

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${CARD_HEIGHT}" viewBox="0 0 ${W} ${CARD_HEIGHT}">
<style>${CSS}
.c{fill:hsl(${c.hue},62%,40%)}@media (prefers-color-scheme: dark){.c{fill:hsl(${c.hue},78%,72%)}}
.bob,.sh,.la,.lb,.al,.ar,.hat{animation-delay:${delay}}
.lb{animation-delay:${-(c.phase % 4) * 0.125 - 0.125}s}
@keyframes shim{0%{transform:translateX(-90px)}100%{transform:translateX(${W + 90}px)}}
</style>
<defs>
<clipPath id="card"><rect x="0" y="0" width="${W}" height="${H}" rx="10"/></clipPath>
<linearGradient id="glow" x1="0" x2="1"><stop offset="0" stop-color="${color}" stop-opacity="0"/><stop offset=".5" stop-color="${color}" stop-opacity=".9"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient>
</defs>
<g clip-path="url(#card)">
<rect width="${W}" height="${H}" fill="${color}" fill-opacity="${isRunning ? 0.14 : 0.07}"/>
<rect width="4" height="${H}" fill="${color}" fill-opacity="${isRunning ? 1 : 0.5}"/>
${isRunning ? `<rect class="shim" x="0" y="${H - 3}" width="90" height="3" fill="url(#glow)"/>` : ''}
</g>
<rect x=".5" y=".5" width="${W - 1}" height="${H - 1}" rx="9.5" fill="none" stroke="${color}" stroke-opacity="${isRunning ? 0.45 : 0.2}"/>
${clawd(c, color)}
<text class="c" x="${TEXT_X}" y="19" font-family="${FONT}" font-size="13" font-weight="600">${xml(fit(c.label, 13, textWidthMax - clockWidth))}</text>
${c.clock ? `<text class="s" x="${W - 14}" y="19" text-anchor="end" font-family="${FONT}" font-size="11" font-variant-numeric="tabular-nums">${xml(c.clock)}</text>` : ''}
<text class="t" x="${TEXT_X}" y="36" font-family="${FONT}" font-size="12">${xml(fit(c.description, 12, textWidthMax))}</text>
${isRunning ? `<circle class="dot fb" cx="${TEXT_X + 3.5}" cy="48.5" r="3.5" fill="${color}"/>` : ''}
<text${lineFill} x="${lineX}" y="52" font-family="${FONT}" font-size="11">${xml(fit(c.line, 11, textWidthMax - (lineX - TEXT_X)))}</text>
</svg>`
}
