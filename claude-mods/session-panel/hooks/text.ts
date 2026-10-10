// Text the panel shows comes from tool inputs and command output, so it can
// hold anything. The engine refuses a whole drawing whose text holds a control
// character, so everything passes through `clean` or `oneLine` first.

// CSI (colors, cursor moves), OSC (titles, links) and two-byte escapes.
const ANSI = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])/g

// Each control character left shows as its Unicode control picture (␛, ␇).
const visible = (s: string): string =>
  s.replace(/[^\P{Cc}\n\t]/gu, ch => {
    const code = ch.charCodeAt(0)
    return code < 0x20 ? String.fromCharCode(0x2400 + code) : code === 0x7f ? '␡' : '�'
  })

/**
 * Terminal output as a reader would have seen it: escape sequences dropped,
 * and a line redrawn with carriage returns (a progress bar) kept as its last
 * state.
 */
export function clean(s: string): string {
  const lines = s
    .replace(ANSI, '')
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(line => line.slice(line.lastIndexOf('\r') + 1))
  return visible(lines.join('\n').replace(/\t/g, '  '))
}

export const oneLine = (s: string): string => clean(s).replace(/\s+/g, ' ').trim()

export const cut = (s: string, max: number): string => (s.length > max ? `${s.slice(0, max - 1)}…` : s)

/** The end of the text, where command output says how it went. */
export function tail(s: string, max: number): string {
  const trimmed = s.replace(/\s+$/, '')
  return trimmed.length > max ? `…${trimmed.slice(-(max - 1))}` : trimmed
}

export function formatDuration(ms: number | undefined): string {
  if (ms === undefined) return '…'
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 59_950) return `${(ms / 1000).toFixed(1)}s`
  return formatClock(ms)
}

export function formatClock(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  const h = Math.floor(s / 3600)
  const mm = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(mm).padStart(2, '0')}:${ss}` : `${mm}:${ss}`
}

export function formatTokens(n: number): string {
  if (n < 1000) return String(n)
  if (n < 999_500) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`
  return `${(n / 1_000_000).toFixed(1)}M`
}

/** The last path segment, which is what names a file at a glance. */
export const baseName = (path: string): string => path.split('/').filter(Boolean).pop() ?? path
