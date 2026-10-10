// A dancing pixel Clawd per running subagent, wearing a party hat in the
// agent's color: 18 by 8 pixels, four frames a second. The terminal draws a
// frame as a Raster of quadrant blocks (two pixels by two per cell, 9 columns
// by 4 rows) and repaints it every beat; the desktop draws the same four
// frames into one SVG and lets CSS show them in turn.

export const DANCER_COLUMNS = 9
export const DANCER_ROWS = 4
/** Milliseconds a frame shows: four beats a second. */
export const BEAT_MS = 250

const W = DANCER_COLUMNS * 2
const H = DANCER_ROWS * 2
const FRAMES = 4
const DEFAULT = 0x01000000
const CLAY = 0xd97757

// Glyphs indexed by the lit quadrants: top-left 1, top-right 2, bottom-left 4, bottom-right 8.
const QUADRANTS = ' ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█'

type Pixels = (number | null)[]

// One frame of four. The hat sways, the arms go up in turn and then
// together, the legs shuffle, and on the off beats the whole Clawd dips.
function pixels(hat: number, frame: number): Pixels {
  const px: Pixels = new Array(W * H).fill(null)
  const beat = frame % FRAMES
  const dip = beat % 2
  const set = (x: number, y: number, color: number | null) => {
    if (y + dip < H) px[(y + dip) * W + x] = color
  }
  const sway = beat === 0 ? -1 : beat === 2 ? 1 : 0
  set(9 + sway, 0, hat)
  for (const x of [8, 9, 10]) set(x + sway, 1, hat)
  for (let y = 2; y <= 5; y++) for (let x = 3; x <= 14; x++) set(x, y, CLAY)
  set(5, 3, null)
  set(12, 3, null)
  const arm = (side: 'left' | 'right', isUp: boolean) => {
    const [outer, inner] = side === 'left' ? [1, 2] : [16, 15]
    if (isUp) {
      set(outer, 2, CLAY)
      set(inner, 3, CLAY)
    } else {
      set(outer, 4, CLAY)
      set(inner, 4, CLAY)
    }
  }
  arm('left', beat === 0 || beat === 3)
  arm('right', beat === 2 || beat === 3)
  for (const x of dip ? [5, 7, 10, 12] : [4, 6, 11, 13]) set(x, 6, CLAY)
  return px
}

function encode(words: Uint32Array): string {
  const bytes = new Uint8Array(words.buffer)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

const hexToInt = (hex: string): number => parseInt(hex.slice(1), 16)
const intToHex = (n: number): string => `#${n.toString(16).padStart(6, '0')}`

const cache = new Map<string, string>()

/** A terminal frame as Raster cells, the hat in the agent's hex color. */
export function dancerCells(hatHex: string, frame: number): string {
  const key = `${hatHex}:${frame % FRAMES}`
  const hit = cache.get(key)
  if (hit !== undefined) return hit
  const px = pixels(hexToInt(hatHex), frame)
  const out = new Uint32Array(DANCER_COLUMNS * DANCER_ROWS * 3)
  for (let row = 0; row < DANCER_ROWS; row++) {
    for (let col = 0; col < DANCER_COLUMNS; col++) {
      const at = (dx: number, dy: number) => px[(row * 2 + dy) * W + col * 2 + dx] ?? null
      const quad = [at(0, 0), at(1, 0), at(0, 1), at(1, 1)]
      // A cell takes one foreground: the hat wins over the body it touches.
      const fg = quad.find(c => c !== null && c !== CLAY) ?? quad.find(c => c !== null) ?? null
      const mask = quad.reduce<number>((m, c, i) => (c !== null ? m | (1 << i) : m), 0)
      const i = (row * DANCER_COLUMNS + col) * 3
      out[i] = QUADRANTS.codePointAt(mask) ?? 0x20
      out[i + 1] = fg ?? DEFAULT
      out[i + 2] = DEFAULT
    }
  }
  const encoded = encode(out)
  cache.set(key, encoded)
  return encoded
}

// The desktop: three CSS pixels a sprite pixel. The band redraws once a
// second while agents run, and a redraw restarts the animation, so the cycle
// is one second long.
const P = 3
const DANCER_WIDTH = W * P
const GAP = 10
export const DANCERS_HEIGHT = H * P

const CSS =
  '.f{opacity:0;animation:f 1s steps(1) infinite}@keyframes f{0%{opacity:1}25%{opacity:0}}' +
  '@media (prefers-reduced-motion: reduce){.f{animation:none}.f0{opacity:1}}'

// A frame as rects, each a run of one color along a row.
function frameRects(px: Pixels): string {
  let out = ''
  for (let y = 0; y < H; y++) {
    let x = 0
    while (x < W) {
      const color = px[y * W + x] ?? null
      let end = x + 1
      while (end < W && (px[y * W + end] ?? null) === color) end++
      if (color !== null) {
        out += `<rect x="${x * P}" y="${y * P}" width="${(end - x) * P}" height="${P}" fill="${intToHex(color)}"/>`
      }
      x = end
    }
  }
  return out
}

function dancerSvg(hatHex: string, index: number): string {
  const hat = hexToInt(hatHex)
  // Frame k shows during the k-th quarter second; each Clawd a beat behind
  // the one before it.
  const frames = Array.from({ length: FRAMES }, (_, k) => {
    const delay = -(((FRAMES - k + index) % FRAMES) * 0.25)
    return `<g class="f f${k}" style="animation-delay:${delay}s">${frameRects(pixels(hat, k))}</g>`
  })
  return `<g transform="translate(${index * (DANCER_WIDTH + GAP)},0)">${frames.join('')}</g>`
}

/** One SVG of the dancers side by side, one hat color each. */
export function dancersSvg(hats: readonly string[]): { source: string; width: number } {
  const width = hats.length * DANCER_WIDTH + Math.max(0, hats.length - 1) * GAP
  const source =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${DANCERS_HEIGHT}" viewBox="0 0 ${width} ${DANCERS_HEIGHT}" shape-rendering="crispEdges">` +
    `<style>${CSS}</style>${hats.map(dancerSvg).join('')}</svg>`
  return { source, width }
}
