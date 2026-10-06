import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { AgentRun, AgentStatus } from '../types'
import { CARD_HEIGHT, cardSvg } from './desktop'
import type { Card } from './desktop'
import { SPRITE_COLUMNS, SPRITE_ROWS, cells, encode, pixels } from './sprite'
import type { Mood } from './sprite'

const PANE = 'subagents'
const TITLE = 'Subagents'
const KEEP = 100
const FRAME_MS = 150
const FRAMES_PER_SECOND = Math.round(1000 / FRAME_MS)

const agents = atom({ plugin: 'subagents', key: 'agents' } as const, [])
const now = atom({ plugin: 'subagents', key: 'now' } as const, 0)
const isAutoOpened = atom({ plugin: 'subagents', key: 'isAutoOpened' } as const, false)

// The first of these input fields that holds a string names the call.
const SUMMARY_FIELDS = [
  'description', 'command', 'file_path', 'notebook_path', 'pattern', 'url',
  'query', 'skill', 'path', 'prompt',
]
const PATH_FIELDS = new Set(['file_path', 'notebook_path', 'path'])

const STATUS_LINE: Record<Exclude<AgentStatus, 'running'>, string> = {
  done: '✓ done',
  stopped: '■ stopped',
  failed: '✗ failed',
}

// Module state is only what the animation needs between frames; session.start
// rebuilds it on every (re)load. Everything the pane draws lives in $.state.
let frame = 0
let running: AgentRun[] = []
let isPaneShown = false
let isRasterDrawn = false

const moodOf = (status: AgentStatus): Mood =>
  status === 'running' ? 'running' : status === 'done' ? 'done' : 'failed'

const hash = (s: string): number => [...s].reduce((h, ch) => (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0, 7)

// A stable hue per agent type, so the same role reads the same in every session.
const hueOf = (type: string): number => hash(type) % 360

function colorOf(type: string): string {
  const hue = hueOf(type)
  const c = 0.55 * (1 - Math.abs(2 * 0.62 - 1))
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1))
  const m = 0.62 - c / 2
  const [r, g, b] =
    hue < 60 ? [c, x, 0] : hue < 120 ? [x, c, 0] : hue < 180 ? [0, c, x]
    : hue < 240 ? [0, x, c] : hue < 300 ? [x, 0, c] : [c, 0, x]
  return '#' + [r, g, b].map(v => Math.round((v + m) * 255).toString(16).padStart(2, '0')).join('')
}

const frameCache = new Map<string, string>()

function spriteCells(mood: Mood, at: number): string {
  const key = mood === 'running' ? `${mood}:${at % 24}` : mood
  let encoded = frameCache.get(key)
  if (encoded === undefined) {
    encoded = encode(cells(pixels(mood, at)))
    frameCache.set(key, encoded)
  }
  return encoded
}

// Each agent walks out of step with the others.
const phaseOf = (a: AgentRun): number => hash(a.id) % 24

const spriteKey = (a: AgentRun): string => `sprite-${a.id}`

function summarize(tool: string, input: Record<string, unknown>): string {
  const name = tool.replace(/^mcp__/, '').replace(/__/g, ' ')
  for (const field of SUMMARY_FIELDS) {
    const value = input[field]
    if (typeof value !== 'string' || value.length === 0) continue
    const text = PATH_FIELDS.has(field) ? (value.split('/').filter(Boolean).pop() ?? value) : value
    return `${name} ${text.replace(/\s+/g, ' ').trim()}`
  }
  return name
}

function formatClock(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  const h = Math.floor(s / 3600)
  const mm = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(mm).padStart(2, '0')}:${ss}` : `${mm}:${ss}`
}

// The engine refuses a whole drawing whose text holds a control character, so
// one escape sequence in a tool input would blank the pane. Rows are one line:
// whitespace collapses, and each control character left shows as its Unicode
// control picture (␛, ␇).
const oneLine = (s: string): string =>
  s.replace(/\s+/g, ' ').trim().replace(/\p{Cc}/gu, ch => {
    const code = ch.charCodeAt(0)
    return code < 0x20 ? String.fromCharCode(0x2400 + code) : code === 0x7f ? '␡' : '�'
  })

// What a row says, on every surface: who, how long, what for, and what now.
function describe(a: AgentRun, at: number, viewing: string | undefined) {
  const label =
    (a.parentAgentId !== undefined ? '↳ ' : '') +
    (a.name !== undefined ? `${a.name} · ${a.type}` : a.type) +
    (viewing !== undefined && viewing === a.agentId ? ' ◂ viewing' : '')
  const tools = `${a.toolCalls} tool ${a.toolCalls === 1 ? 'call' : 'calls'}`
  const line = a.status === 'running' ? a.activity || 'starting…' : `${STATUS_LINE[a.status]} · ${tools}`
  return {
    label: oneLine(label),
    clock: formatClock((a.endedAt ?? at) - a.startedAt),
    description: oneLine(a.description) || '—',
    line: oneLine(line),
  }
}

function remember(list: AgentRun[]): void {
  running = list.filter(a => a.status === 'running')
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'subagents',
      description: 'Show or hide the pane of this session\'s subagents',
    })
    remember(await read($, agents))

    // The frame clock: walks the running agents' sprites by blitting their
    // Rasters, and once a second ticks the elapsed times. Idle, it does nothing.
    $.clock.every(FRAME_MS, () => {
      void (async () => {
        if (running.length === 0) return
        frame++
        if (frame % FRAMES_PER_SECOND === 0) {
          const at = await $.clock.now()
          await update($, now, () => at)
          isPaneShown = (await $.ui.panes()).some(p => p.id === PANE && p.isShown)
        }
        if (!isPaneShown || !isRasterDrawn) return
        await Promise.all(
          running.map(a =>
            $.ui.blit({ requestId: PANE, key: spriteKey(a), cells: spriteCells('running', frame + phaseOf(a)) }),
          ),
        )
      })()
    })
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') remember(await update($, agents, () => []))
    return next(e)
  })

  on('command.run', { command: 'subagents' }, async $ => {
    // An unasked open waits undrawn on a narrow terminal: only a shown pane closes.
    if ((await $.ui.panes()).some(p => p.id === PANE && p.isPlaced && p.isShown)) {
      await $.ui.close({ id: PANE })
      return { text: 'Subagents pane closed.' }
    }
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: 'Subagents pane opened.' }
  })

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    if (started.deny !== undefined) return started

    const at = await $.clock.now()
    const run: AgentRun = {
      id: started.agentId ?? e.tool_use_id,
      agentId: started.agentId,
      parentAgentId: e.parentAgentId,
      type: e.subagentType,
      name: e.name,
      description: e.description,
      status: 'running',
      activity: '',
      toolCalls: 0,
      startedAt: at,
    }
    remember(await update($, agents, list => [...list.filter(a => a.id !== run.id), run].slice(-KEEP)))
    await update($, now, () => at)
    if (!(await read($, isAutoOpened))) {
      await update($, isAutoOpened, () => true)
      void $.ui.open({ id: PANE, title: TITLE })
    }
    return started
  })

  // A subagent's tool calls carry its loop id: the latest one is its status.
  on('tool.call', async ($, e, next) => {
    const agentId = e.agentId
    if (agentId !== undefined && (await read($, agents)).some(a => a.agentId === agentId)) {
      const activity = summarize(String(e.tool), e as unknown as Record<string, unknown>)
      remember(
        await update($, agents, list =>
          list.map(a =>
            a.agentId === agentId
              ? { ...a, activity, toolCalls: a.toolCalls + 1, status: 'running', endedAt: undefined }
              : a,
          ),
        ),
      )
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const agentId = e.agentId
    if (agentId !== undefined) {
      const at = await $.clock.now()
      const status: AgentStatus = e.reason === 'answer' ? 'done' : e.reason === 'aborted' ? 'stopped' : 'failed'
      remember(
        await update($, agents, list =>
          list.map(a => (a.agentId === agentId && a.status === 'running' ? { ...a, status, endedAt: at } : a)),
        ),
      )
      await update($, now, () => at)
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, agents)
    const at = Math.max(await read($, now), ...list.map(a => a.startedAt))
    isPaneShown = true
    isRasterDrawn = e.surface === 'terminal'

    // Running agents first, then finished ones, newest first within each.
    const newest = [...list].reverse()
    const live = newest.filter(a => a.status === 'running')
    const ended = newest.filter(a => a.status !== 'running')
    const shown = [...live, ...ended]
    const header = (
      <Text bold>
        {live.length} running · {ended.length} finished
      </Text>
    )
    const viewing = e.props.view.agentId

    // Desktop, VS Code and mobile: one SVG card per agent.
    if (e.surface !== 'terminal') {
      const { Svg } = $.ui.resolve(e)
      const width = Math.max(240, Math.min(900, e.props.bodyColumns * 8 - 8))
      const second = Math.floor(at / 1000)
      if (list.length === 0) {
        const idle: Card = {
          width, hue: 18, status: 'idle', label: 'No subagents yet.', clock: '',
          description: 'Agents this session starts show up here.', line: '', phase: 0, isBlinking: false,
        }
        return <Svg source={cardSvg(idle)} alt="No subagents yet." width={width} height={CARD_HEIGHT} />
      }
      return (
        <Box flexDirection="column">
          {header}
          {shown.map(a => {
            const text = describe(a, at, viewing)
            const card: Card = {
              width, hue: hueOf(a.type), status: a.status, ...text,
              phase: phaseOf(a), isBlinking: a.status === 'running' && (second + phaseOf(a)) % 4 === 0,
            }
            return (
              <Svg key={a.id} source={cardSvg(card)} alt={`${text.label}: ${text.description}, ${text.line}`} width={width} height={CARD_HEIGHT} />
            )
          })}
        </Box>
      )
    }

    // The terminal: a Raster sprite beside three lines of text.
    const { Raster } = $.ui.resolve(e)
    const textColumns = Math.max(12, e.props.bodyColumns - SPRITE_COLUMNS - 1)
    const sprite = (key: string, mood: Mood, at: number) => (
      <Raster key={key} columns={SPRITE_COLUMNS} rows={SPRITE_ROWS} cells={spriteCells(mood, at)} />
    )
    if (list.length === 0) {
      return (
        <Box flexDirection="row" gap={1}>
          {sprite('sprite-idle', 'done', 0)}
          <Box flexDirection="column" width={textColumns}>
            <Text bold>No subagents yet.</Text>
            <Text dimColor wrap="wrap">Agents this session starts show up here.</Text>
          </Box>
        </Box>
      )
    }
    return (
      <Box flexDirection="column">
        {header}
        <Box flexDirection="column" marginTop={1}>
          {shown.map(a => {
            const text = describe(a, at, viewing)
            return (
              <Box key={a.id} flexDirection="row" gap={1} marginBottom={1}>
                {sprite(spriteKey(a), moodOf(a.status), frame + phaseOf(a))}
                <Box flexDirection="column" width={textColumns}>
                  <Text wrap="truncate-end">
                    <Text bold color={colorOf(a.type)}>{text.label}</Text>
                    <Text dimColor> {text.clock}</Text>
                  </Text>
                  <Text wrap="truncate-end">{text.description}</Text>
                  <Text wrap="truncate-end" color={a.status === 'failed' ? 'red' : undefined} dimColor={a.status !== 'failed'}>
                    {a.status === 'running' ? `● ${text.line}` : text.line}
                  </Text>
                </Box>
              </Box>
            )
          })}
        </Box>
      </Box>
    )
  })
}
