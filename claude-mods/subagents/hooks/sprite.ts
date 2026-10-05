// A pixel Clawd drawn with quadrant blocks, two pixels by two per cell, the way
// Claude Code's own startup logo is: 18 by 6 pixels, 9 columns by 3 rows.

export const SPRITE_COLUMNS = 9
export const SPRITE_ROWS = 3

const W = SPRITE_COLUMNS * 2
const H = SPRITE_ROWS * 2
const DEFAULT = 0x01000000

const CLAY = 0xd97757
const RESTING = 0xa8705c
const ASH = 0x8a8580

export type Mood = 'running' | 'done' | 'failed'

type Pixels = (number | null)[]

// Glyphs indexed by the lit quadrants: top-left 1, top-right 2, bottom-left 4, bottom-right 8.
const QUADRANTS = ' ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█'

function body(px: Pixels, color: number, isBlinking: boolean, legs: number[], armLift: [number, number]): void {
  const span = (x0: number, x1: number, y: number) => {
    for (let x = x0; x <= x1; x++) px[y * W + x] = color
  }
  for (let y = 0; y < 4; y++) span(3, 14, y)
  if (!isBlinking) {
    px[W + 5] = null
    px[W + 12] = null
  }
  span(1, 2, 2 - armLift[0])
  span(15, 16, 2 - armLift[1])
  for (const x of legs) px[4 * W + x] = color
}

// One frame of the sprite as pixels. A running Clawd shuffles its legs and
// swings one arm, then the other, every four frames; now and then it blinks.
export function pixels(mood: Mood, frame: number): Pixels {
  const px: Pixels = new Array(W * H).fill(null)
  if (mood !== 'running') {
    body(px, mood === 'failed' ? ASH : RESTING, false, [4, 6, 11, 13], [0, 0])
    return px
  }
  const step = frame % 4
  const legs = step % 2 === 0 ? [4, 6, 11, 13] : [5, 7, 10, 12]
  const arms: [number, number] = step === 1 ? [1, 0] : step === 3 ? [0, 1] : [0, 0]
  body(px, CLAY, frame % 24 === 23, legs, arms)
  return px
}

// Packs pixels into Raster cells: one quadrant glyph per 2x2 block, lit pixels
// in the foreground, the rest the terminal's own background.
export function cells(px: Pixels): Uint32Array {
  const out = new Uint32Array(SPRITE_COLUMNS * SPRITE_ROWS * 3)
  for (let row = 0; row < SPRITE_ROWS; row++) {
    for (let col = 0; col < SPRITE_COLUMNS; col++) {
      const at = (dx: number, dy: number) => px[(row * 2 + dy) * W + col * 2 + dx] ?? null
      const quad = [at(0, 0), at(1, 0), at(0, 1), at(1, 1)]
      const fg = quad.find(c => c !== null) ?? null
      const mask = quad.reduce<number>((m, c, i) => (c !== null ? m | (1 << i) : m), 0)
      const i = (row * SPRITE_COLUMNS + col) * 3
      out[i] = QUADRANTS.codePointAt(mask) ?? 0x20
      out[i + 1] = fg ?? DEFAULT
      out[i + 2] = DEFAULT
    }
  }
  return out
}

export function encode(words: Uint32Array): string {
  const bytes = new Uint8Array(words.buffer)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}
