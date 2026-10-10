import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, StateDollar } from 'claude-code'

import type {
  AgentRun, AgentStatus, CallMark, CallStatus, FileTouch, ShellRun, ShellStatus, Tab, TraceStep,
} from '../types'
import { agentAskText, shellAskText } from './ask'
import { BEAT_MS, DANCERS_HEIGHT, DANCER_COLUMNS, DANCER_ROWS, dancerCells, dancersSvg } from './dancer'
import { demo } from './demo'
import { AGENT_CARD_HEIGHT, AXIS_HEIGHT, LANE_HEIGHT, TONE, agentCardSvg, agentColor, axisSvg, laneSvg, tilesSvg } from './svg'
import type { Lane, Span, Tile } from './svg'
import { baseName, clean, cut, formatClock, formatDuration, formatTokens, oneLine, tail } from './text'

const PANE = 'session-panel'
const TITLE = 'Session'
const KEEP_CALLS = 1500
const KEEP_SHELL = 150
const KEEP_AGENTS = 60
const KEEP_TRACE = 40
const KEEP_FILES = 300
const STDOUT_CHARS = 4000
const STDERR_CHARS = 2000
const PROMPT_CHARS = 4000
const ANSWER_CHARS = 8000
const TIMELINE_AGENTS = 10
// Agent rows the band above the prompt shows before `+N more`.
const BAND_AGENTS = 3
const SPINNER = '◐◓◑◒'
// The width of the timeline's label column, and the CSS pixels a column takes.
const LANE_LABEL_COLUMNS = 20
const PX_PER_COLUMN = 8

const calls = atom({ plugin: 'session-panel', key: 'calls' } as const, [])
const shell = atom({ plugin: 'session-panel', key: 'shell' } as const, [])
const agents = atom({ plugin: 'session-panel', key: 'agents' } as const, [])
const files = atom({ plugin: 'session-panel', key: 'files' } as const, [])
const usage = atom({ plugin: 'session-panel', key: 'usage' } as const, { tokensIn: 0, tokensOut: 0, turns: 0 })
const tab = atom({ plugin: 'session-panel', key: 'tab' } as const, 'overview')
const expanded = atom({ plugin: 'session-panel', key: 'expanded' } as const, [])
const now = atom({ plugin: 'session-panel', key: 'now' } as const, 0)
const asked = atom({ plugin: 'session-panel', key: 'asked' } as const, [])
const turnFrom = atom({ plugin: 'session-panel', key: 'turnFrom' } as const, 0)

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'subagents', label: 'Subagents' },
  { id: 'shell', label: 'Shell' },
  { id: 'files', label: 'Files' },
]

const SHELL_TOOLS = new Set(['Bash', 'PowerShell'])
const READ_TOOLS = new Set(['Read', 'NotebookRead'])
const EDIT_TOOLS = new Set(['Edit', 'MultiEdit', 'Write', 'NotebookEdit'])

// The first of these input fields that holds a string names the call.
const SUMMARY_FIELDS = [
  'description', 'command', 'file_path', 'notebook_path', 'pattern', 'url',
  'query', 'skill', 'path', 'prompt',
]
const PATH_FIELDS = new Set(['file_path', 'notebook_path', 'path'])

// Terminal colors are theme keys, so the pane follows the person's theme.
const CALL_GLYPH: Record<ShellStatus, { glyph: string; color: string }> = {
  running: { glyph: '◌', color: 'warning' },
  ok: { glyph: '✓', color: 'success' },
  error: { glyph: '✗', color: 'error' },
  denied: { glyph: '⊘', color: 'warning' },
  background: { glyph: '↗', color: 'suggestion' },
}
const AGENT_GLYPH: Record<AgentStatus, { glyph: string; color: string }> = {
  running: { glyph: '●', color: 'warning' },
  done: { glyph: '✓', color: 'success' },
  stopped: { glyph: '■', color: 'subtle' },
  failed: { glyph: '✗', color: 'error' },
}

// Timeline colors per kind of call, as on the activity pane.
const KINDS: { match: RegExp; color: string }[] = [
  { match: /^(Bash|PowerShell)$/, color: '#2fa39a' },
  { match: /^(Read|NotebookRead)$/, color: '#5b8def' },
  { match: /^(Edit|MultiEdit|Write|NotebookEdit)$/, color: '#3b9c5f' },
  { match: /^(Grep|Glob|LS)$/, color: '#9a6fe0' },
  { match: /^Web/, color: '#d9a23b' },
  { match: /^(Agent|Task)$/, color: '#d97757' },
  { match: /^Skill$/, color: '#c2569b' },
  { match: /^mcp__/, color: '#c2569b' },
]
const kindColor = (tool: string): string => KINDS.find(k => k.match.test(tool))?.color ?? TONE.plain

function summarize(tool: string, input: Record<string, unknown>): string {
  const name = tool.replace(/^mcp__/, '').replace(/__/g, ' ')
  for (const field of SUMMARY_FIELDS) {
    const value = input[field]
    if (typeof value !== 'string' || value.length === 0) continue
    return oneLine(`${name} ${PATH_FIELDS.has(field) ? baseName(value) : value}`)
  }
  return name
}

const isOpen = (status: string) => status === 'running'

// Markdown read as one plain line: headings, list markers, emphasis and code
// marks dropped.
const plainText = (md: string): string =>
  md.replace(/^\s*(#+|[-*+]|\d+\.)\s+/gm, '').replace(/[`*_]+/g, '')

const askStatus = (count: number): string | undefined =>
  count === 0 ? undefined : `session panel: ${count} attached to your next prompt`

// The terminal band's dancers and the site they show in, repainted every
// beat while it shows them; the desktop's dance by CSS instead.
let bandSite: string | undefined
let bandDancers: { key: string; hat: string }[] = []
let beat = 0

// Whether anything still runs, so the clock ticks only while it matters.
let isLive = false

async function refreshLive($: StateDollar): Promise<void> {
  const [s, a] = await Promise.all([read($, shell), read($, agents)])
  isLive = s.some(r => isOpen(r.status)) || a.some(r => isOpen(r.status))
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'panel',
      description: 'Show or hide the session panel; `/panel demo` loads sample data, `/panel clear` empties it',
    })
    await refreshLive($)
    $.clock.every(BEAT_MS, () => {
      const site = bandSite
      if (site === undefined || bandDancers.length === 0) return
      beat++
      void Promise.all(
        bandDancers.map(d => $.ui.blit({ requestId: site, key: d.key, cells: dancerCells(d.hat, beat) })),
      ).catch(() => undefined)
    })
    $.clock.every(1000, () => {
      if (!isLive) return
      void (async () => {
        const at = await $.clock.now()
        await update($, now, () => at)
      })()
    })
    return next(e)
  })

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') await reset($)
    return next(e)
  })

  on('command.run', { command: 'panel' }, async ($, e) => {
    const arg = e.args.trim()
    if (arg === 'demo') {
      const at = await $.clock.now()
      const sample = demo(at)
      await Promise.all([
        update($, calls, () => sample.calls),
        update($, shell, () => sample.shell),
        update($, agents, () => sample.agents),
        update($, files, () => sample.files),
        update($, usage, () => sample.usage),
        update($, now, () => at),
        update($, turnFrom, () => 0),
      ])
      await refreshLive($)
      await $.ui.open({ id: PANE, title: TITLE })
      return { text: 'Session panel opened with sample data. `/panel clear` empties it.' }
    }
    if (arg === 'clear') {
      await reset($)
      await $.ui.status(undefined)
      return { text: 'Session panel cleared.' }
    }
    if ((await $.ui.panes()).some(p => p.id === PANE && p.isPlaced && p.isShown)) {
      await $.ui.close({ id: PANE })
      return { text: 'Session panel closed.' }
    }
    await $.ui.open({ id: PANE, title: TITLE })
    return { text: 'Session panel opened.' }
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
      description: oneLine(e.description),
      prompt: cut(clean(e.prompt), PROMPT_CHARS),
      model: started.model,
      isBackground: e.background,
      status: 'running',
      startedAt: at,
      toolCalls: 0,
      trace: [],
      tokensIn: 0,
      tokensOut: 0,
    }
    await update($, agents, list => [...list.filter(a => a.id !== run.id), run].slice(-KEEP_AGENTS))
    await update($, now, () => at)
    isLive = true
    return started
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const startedAt = await $.clock.now()
    const input = e as unknown as Record<string, unknown>
    const tool = String(e.tool)
    const id = e.tool_use_id ?? `${tool}-${startedAt}-${Math.random()}`
    const agentId = e.agentId
    const isShell = SHELL_TOOLS.has(tool)

    await update($, calls, list => [...list, { id, tool, agentId, status: 'running' as const, startedAt }].slice(-KEEP_CALLS))
    if (isShell) {
      const run: ShellRun = {
        id, agentId, status: 'running', startedAt, stdout: '', stderr: '',
        command: clean(String(input.command ?? '')),
        description: oneLine(String(input.description ?? '')),
      }
      await update($, shell, list => [...list, run].slice(-KEEP_SHELL))
      isLive = true
    }
    if (agentId !== undefined) {
      const step: TraceStep = { id, tool, summary: summarize(tool, input), status: 'running', at: startedAt }
      await update($, agents, list =>
        list.map(a =>
          a.agentId === agentId
            ? { ...a, status: 'running' as const, endedAt: undefined, toolCalls: a.toolCalls + 1, trace: [...a.trace, step].slice(-KEEP_TRACE) }
            : a,
        ),
      )
    }

    const ran = await next(e)

    const endedAt = await $.clock.now()
    const status: CallStatus = ran.deny !== undefined ? 'denied' : ran.isError === true ? 'error' : 'ok'
    await update($, calls, list => list.map(c => (c.id === id ? { ...c, status, endedAt } : c)))
    if (agentId !== undefined) {
      await update($, agents, list =>
        list.map(a =>
          a.agentId === agentId ? { ...a, trace: a.trace.map(s => (s.id === id ? { ...s, status } : s)) } : a,
        ),
      )
    }
    if (isShell) {
      const result = (ran as { result?: unknown }).result
      const out = typeof result === 'object' && result !== null ? (result as Record<string, unknown>) : {}
      const isBackground = typeof out.backgroundTaskId === 'string'
      const stdout = typeof out.stdout === 'string' ? out.stdout : ''
      // An errored call stores its error text, which holds the command's output.
      const stderr = typeof out.stderr === 'string' ? out.stderr : status === 'error' ? (ran.text ?? '') : ''
      const note =
        ran.deny ??
        (out.interrupted === true ? 'Interrupted' : undefined) ??
        (typeof out.timedOutAfterMs === 'number' ? `Timed out after ${formatDuration(out.timedOutAfterMs)}; moved to the background` : undefined) ??
        (isBackground ? 'Running in the background' : undefined) ??
        (typeof out.returnCodeInterpretation === 'string' ? out.returnCodeInterpretation : undefined)
      await update($, shell, list =>
        list.map(r =>
          r.id === id
            ? {
                ...r, endedAt, status: (isBackground && status === 'ok' ? 'background' : status) as ShellStatus,
                stdout: tail(clean(stdout), STDOUT_CHARS), stderr: tail(clean(stderr), STDERR_CHARS),
                note: note === undefined ? undefined : oneLine(note),
              }
            : r,
        ),
      )
      await refreshLive($)
    }
    const path = input.file_path ?? input.notebook_path
    if (status === 'ok' && typeof path === 'string' && (READ_TOOLS.has(tool) || EDIT_TOOLS.has(tool))) {
      const isEdit = EDIT_TOOLS.has(tool)
      await update($, files, list => {
        const old = list.find(f => f.path === path)
        const touch: FileTouch = {
          path,
          reads: (old?.reads ?? 0) + (isEdit ? 0 : 1),
          edits: (old?.edits ?? 0) + (isEdit ? 1 : 0),
          lastAt: endedAt,
        }
        return [...list.filter(f => f.path !== path), touch].slice(-KEEP_FILES)
      })
    }
    return ran
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const at = await $.clock.now()
    const u = e.usage
    const tokensIn = u ? u.input_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens : 0
    const tokensOut = u ? u.output_tokens : 0
    await update($, usage, old => ({
      tokensIn: old.tokensIn + tokensIn,
      tokensOut: old.tokensOut + tokensOut,
      turns: old.turns + (e.agentId === undefined ? 1 : 0),
    }))
    const agentId = e.agentId
    if (agentId !== undefined) {
      const status: AgentStatus = e.reason === 'answer' ? 'done' : e.reason === 'aborted' ? 'stopped' : 'failed'
      await update($, agents, list =>
        list.map(a =>
          a.agentId === agentId
            ? {
                ...a, status, endedAt: at, model: u?.model ?? a.model,
                answer: e.answer ? cut(clean(e.answer), ANSWER_CHARS) : a.answer,
                tokensIn: a.tokensIn + tokensIn, tokensOut: a.tokensOut + tokensOut,
              }
            : a,
        ),
      )
      await update($, now, () => at)
      await refreshLive($)
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  // Each armed row's details ride the next prompt the person sends, once.
  on('prompt.submit', async ($, e, next) => {
    if (!e.text.trimStart().startsWith('/')) {
      const at = await $.clock.now()
      await update($, turnFrom, () => at)
    }
    const ids = await read($, asked)
    if (ids.length === 0 || e.text.trimStart().startsWith('/')) return next(e)
    const [shellList, agentList] = await Promise.all([read($, shell), read($, agents)])
    const texts = ids.flatMap(id => {
      const run = shellList.find(r => r.id === id)
      if (run !== undefined) return [shellAskText(run)]
      const agent = agentList.find(a => a.id === id)
      return agent !== undefined ? [agentAskText(agent)] : []
    })
    const result = await next(texts.length === 0 ? e : { ...e, context: [...(e.context ?? []), ...texts] })
    if (result.drop === undefined) {
      await update($, asked, () => [])
      await $.ui.status(undefined)
    }
    return result
  }).catch(($, e, next) => next(e))

  // A popup above the prompt: this turn's subagents while they work, and how
  // they ended until the next prompt. Other mods' rows stay beneath it.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const [agentList, from, clock] = await Promise.all([read($, agents), read($, turnFrom), read($, now)])
    const shown = agentList.filter(a => a.status === 'running' || (a.endedAt ?? 0) > from)
    if (shown.length === 0) return next(e)

    const { Box, Text, Button } = $.ui.resolve(e)
    const Raster = e.surface === 'terminal' ? $.ui.resolve(e).Raster : undefined
    const Svg = e.surface === 'desktop' ? $.ui.resolve(e).Svg : undefined
    const below = await next(e)
    const at = Math.max(clock, ...shown.map(a => a.startedAt))
    // Rows only for what needs an eye: running agents, then failed ones.
    // Finished ones fold into the header's count.
    const live = shown.filter(a => a.status === 'running')
    const failed = shown.filter(a => a.status === 'failed')
    const done = shown.length - live.length - failed.length
    const listed = [...live, ...failed]

    // A dancing Clawd per running agent, in its hat color, left of the rows.
    const dancers = live.slice(0, BAND_AGENTS).map(a => ({ key: `dancer-${a.id}`, hat: agentColor(a.type) }))
    const isDancing = dancers.length > 0 && e.props.bodyColumns >= 60
    const desktopFloor = Svg !== undefined && isDancing ? dancersSvg(dancers.map(d => d.hat)) : undefined
    if (Raster !== undefined) {
      bandSite = isDancing ? e.requestId : undefined
      bandDancers = isDancing ? dancers : []
    }
    const floor = !isDancing ? null : Raster !== undefined ? (
      <Box flexDirection="row" gap={1}>
        {dancers.map(d => <Raster key={d.key} columns={DANCER_COLUMNS} rows={DANCER_ROWS} cells={dancerCells(d.hat, beat)} />)}
      </Box>
    ) : Svg !== undefined && desktopFloor !== undefined ? (
      <Svg source={desktopFloor.source} alt={dancers.length === 1 ? 'A Clawd dancing' : `${dancers.length} Clawds dancing`} width={desktopFloor.width} height={DANCERS_HEIGHT} />
    ) : null
    const floorColumns = !isDancing ? 0 : Raster !== undefined ? dancers.length * (DANCER_COLUMNS + 1) : Math.ceil((desktopFloor?.width ?? 0) / 8) + 1
    const columns = Math.max(20, e.props.bodyColumns - floorColumns)
    const rows = listed.slice(0, Math.max(1, Math.min(BAND_AGENTS, e.props.maxRows - 2)))
    const spin = SPINNER[Math.floor(at / 1000) % SPINNER.length] ?? '·'
    const summary = [
      live.length > 0 ? `${live.length} running` : undefined,
      failed.length > 0 ? `${failed.length} failed` : undefined,
      done > 0 ? `${done} done` : undefined,
    ].filter(Boolean).join(' · ')

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1} alignItems="center">
          {floor}
          <Box flexDirection="column" flexGrow={1}>
            <Box flexDirection="row">
              <Text dimColor>subagents · {summary}</Text>
              <Box flexGrow={1} />
              <Button key="band-open" plain dimColor label="open ›" onPress={() => showInPanel($, 'subagents')} />
            </Box>
            {rows.map(a => {
              const isRunning = a.status === 'running'
              const latest = a.trace[a.trace.length - 1]
              const doing = isRunning ? latest?.summary ?? 'starting…' : 'failed'
              const name = cut(a.name ?? a.type, Math.max(8, Math.floor(columns * 0.28)))
              return (
                <Box key={`band-${a.id}`} flexDirection="row">
                  <Text color={isRunning ? agentColor(a.type) : 'error'}>
                    {a.parentAgentId !== undefined ? '  ' : ''}{isRunning ? spin : '✗'}{' '}
                  </Text>
                  <Button key={`band-agent-${a.id}`} plain label={name} onPress={() => showInPanel($, 'subagents', a.id)} />
                  <Text dimColor wrap="truncate-end">  {cut(oneLine(doing), Math.max(6, Math.floor(columns * 0.45)))}</Text>
                  <Box flexGrow={1} />
                  <Text dimColor>{formatClock((a.endedAt ?? at) - a.startedAt)}</Text>
                </Box>
              )
            })}
            {listed.length > rows.length && <Text dimColor>  +{listed.length - rows.length} more</Text>}
          </Box>
        </Box>
        {below}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Code, Markdown } = $.ui.resolve(e)
    const Svg = e.surface === 'terminal' ? undefined : $.ui.resolve(e).Svg
    const [current, open, callList, shellList, agentList, fileList, totals, clock, armed] = await Promise.all([
      read($, tab), read($, expanded), read($, calls), read($, shell), read($, agents), read($, files), read($, usage), read($, now),
      read($, asked),
    ])
    const at = Math.max(clock, ...callList.map(c => c.endedAt ?? c.startedAt), ...agentList.map(a => a.startedAt))
    const isOpenRow = new Set(open)
    const width = Math.max(260, Math.min(980, e.props.bodyColumns * 8 - 8))
    const columns = e.props.bodyColumns

    const toggle = (id: string) =>
      update($, expanded, ids => (ids.includes(id) ? ids.filter(one => one !== id) : [...ids, id]))
    // Switches tab and lands on the row asked for, or on the tab's top.
    const show = (next: Tab, id?: string) => showInPanel($, next, id)
    const isArmed = new Set(armed)
    const toggleAsk = async (id: string) => {
      const ids = await update($, asked, list => (list.includes(id) ? list.filter(one => one !== id) : [...list, id]))
      await $.ui.status(askStatus(ids.length))
    }
    // Arms the row: its details ride the next prompt as context.
    const askButton = (id: string) => (
      <Button key={`ask-${id}`} plain dimColor={!isArmed.has(id)} label={isArmed.has(id) ? '✓ asked' : 'ask'} onPress={() => toggleAsk(id)} />
    )
    const rule = (key: string) => (
      <Text key={`rule-${key}`} dimColor wrap="truncate-end">{'─'.repeat(Math.max(1, columns))}</Text>
    )

    const agentById = new Map(agentList.filter(a => a.agentId).map(a => [a.agentId as string, a]))
    const agentLabel = (a: AgentRun) => (a.name ? `${a.name} · ${a.type}` : a.type)
    const runningShell = shellList.filter(r => r.status === 'running').length
    const failedShell = shellList.filter(r => r.status === 'error').length
    const runningAgents = agentList.filter(a => a.status === 'running').length
    const failedAgents = agentList.filter(a => a.status === 'failed').length

    const tabBar = (
      <Box flexDirection="row" gap={2}>
        {TABS.map(t => {
          const count =
            t.id === 'subagents' ? agentList.length : t.id === 'shell' ? shellList.length : t.id === 'files' ? fileList.length : undefined
          const alert = (t.id === 'shell' && failedShell > 0) || (t.id === 'subagents' && failedAgents > 0) ? ' •' : ''
          return (
            <Button
              key={`tab-${t.id}`}
              plain
              dimColor={t.id !== current}
              label={count === undefined ? t.label : `${t.label} ${count}${alert}`}
              onPress={() => show(t.id)}
            />
          )
        })}
      </Box>
    )

    // ── Overview ────────────────────────────────────────────────────────────
    const overview = () => {
      const failedCalls = callList.filter(c => c.status === 'error' || c.status === 'denied').length
      const tiles: Tile[] = [
        {
          label: 'Tool calls', value: String(callList.length),
          detail: failedCalls > 0 ? `${failedCalls} failed or denied` : `${totals.turns} turns`,
          tone: failedCalls > 0 ? 'bad' : 'ok',
        },
        {
          label: 'Shell', value: String(shellList.length),
          detail: failedShell > 0 ? `${failedShell} failed` : runningShell > 0 ? `${runningShell} running` : 'all passed',
          tone: failedShell > 0 ? 'bad' : runningShell > 0 ? 'run' : 'ok',
        },
        {
          label: 'Subagents', value: String(agentList.length),
          detail: runningAgents > 0 ? `${runningAgents} running` : failedAgents > 0 ? `${failedAgents} failed` : 'none running',
          tone: runningAgents > 0 ? 'run' : failedAgents > 0 ? 'bad' : 'ok',
        },
        {
          label: 'Tokens', value: formatTokens(totals.tokensIn + totals.tokensOut),
          detail: `${formatTokens(totals.tokensIn)} in · ${formatTokens(totals.tokensOut)} out`, tone: 'plain',
        },
      ]

      const attention = [
        ...shellList.filter(r => r.status === 'error').map(r => ({
          id: r.id, at: r.startedAt, tab: 'shell' as const, text: `✗ ${r.description || cut(oneLine(r.command), 60)}`,
        })),
        ...agentList.filter(a => a.status === 'failed').map(a => ({
          id: a.id, at: a.startedAt, tab: 'subagents' as const, text: `✗ ${agentLabel(a)} · ${a.description}`,
        })),
      ].sort((x, y) => y.at - x.at).slice(0, 5)

      const attentionList = attention.length > 0 && (
        <Box flexDirection="column">
          {rule('attention')}
          <Text bold>Needs attention</Text>
          {attention.map(item => (
            <Button key={`attn-${item.id}`} plain label={item.text} onPress={() => show(item.tab, item.id)} />
          ))}
        </Box>
      )

      if (Svg === undefined) {
        return (
          <Box flexDirection="column" gap={1}>
            {tiles.map(t => (
              <Text key={`tile-${t.label}`}>
                <Text bold>{t.label.padEnd(10)}</Text> {t.value.padStart(6)}  <Text dimColor>{t.detail}</Text>
              </Text>
            ))}
            {attentionList}
          </Box>
        )
      }

      const drawnTiles = tilesSvg(tiles, width)
      const shown = [...agentList].sort((a, b) => a.startedAt - b.startedAt).slice(-TIMELINE_AGENTS)
      const from = Math.min(at - 60_000, ...callList.map(c => c.startedAt), ...shown.map(a => a.startedAt))
      const tick = (c: CallMark): Span => ({
        start: c.startedAt, end: c.endedAt, color: kindColor(c.tool), isFailed: c.status === 'error',
      })
      // Each row: its label (a Button when it leads somewhere) and its strip.
      type Row = { key: string; label: string; lane: Lane; onPress?: () => unknown }
      const rows: Row[] = [
        {
          key: 'shell', label: 'Shell', onPress: () => show('shell'),
          lane: {
            color: kindColor('Bash'), ticks: [],
            spans: shellList.filter(r => r.agentId === undefined).map(r => ({
              start: r.startedAt, end: r.status === 'running' ? undefined : r.endedAt, color: kindColor('Bash'),
              isFailed: r.status === 'error',
            })),
          },
        },
        {
          key: 'main', label: 'Main tools',
          lane: { color: TONE.plain, spans: [], ticks: callList.filter(c => c.agentId === undefined && !SHELL_TOOLS.has(c.tool)).map(tick) },
        },
        ...shown.map(a => ({
          key: a.id,
          label: `${a.parentAgentId ? '↳ ' : ''}${agentLabel(a)}`,
          onPress: () => show('subagents', a.id),
          lane: {
            color: agentColor(a.type),
            spans: [{
              start: a.startedAt, end: a.status === 'running' ? undefined : (a.endedAt ?? at), color: agentColor(a.type),
              isFailed: a.status === 'failed',
            }],
            ticks: callList.filter(c => c.agentId === a.agentId).map(tick),
          },
        })),
      ]
      const labelColumns = Math.min(LANE_LABEL_COLUMNS, Math.floor(columns * 0.3))
      const stripWidth = width - labelColumns * PX_PER_COLUMN

      return (
        <Box flexDirection="column" gap={1}>
          <Svg source={drawnTiles.source} alt={tiles.map(t => `${t.label} ${t.value}, ${t.detail}`).join('; ')} width={width} height={drawnTiles.height} />
          <Box flexDirection="column">
            <Box flexDirection="row">
              <Box width={labelColumns}>
                <Text bold>Timeline</Text>
              </Box>
              <Svg source={axisSvg(from, at, stripWidth)} alt={`Time axis over ${formatClock(at - from)}`} width={stripWidth} height={AXIS_HEIGHT} />
            </Box>
            {rows.map((row, i) => {
              const label = cut(row.label, labelColumns - 2)
              return (
                <Box key={`lane-row-${row.key}`} flexDirection="row" alignItems="center">
                  <Box width={labelColumns}>
                    {row.onPress !== undefined ? (
                      <Button key={`lane-${row.key}`} plain label={label} onPress={row.onPress} />
                    ) : (
                      <Text dimColor wrap="truncate-end">{label}</Text>
                    )}
                  </Box>
                  <Svg source={laneSvg(row.lane, from, at, stripWidth, i % 2 === 0)} alt={`${row.label} lane`} width={stripWidth} height={LANE_HEIGHT} />
                </Box>
              )
            })}
          </Box>
          {attentionList}
        </Box>
      )
    }

    // ── Subagents ───────────────────────────────────────────────────────────
    const subagents = () => {
      if (agentList.length === 0) return <Text dimColor>No subagents yet. Agents this session starts show up here.</Text>

      // Tree order: roots newest first, each followed by its children.
      const children = new Map<string | undefined, AgentRun[]>()
      for (const a of agentList) {
        const parent = a.parentAgentId !== undefined && agentById.has(a.parentAgentId) ? a.parentAgentId : undefined
        children.set(parent, [...(children.get(parent) ?? []), a])
      }
      const ordered: { a: AgentRun; depth: number }[] = []
      const walk = (parent: string | undefined, depth: number) => {
        const list = [...(children.get(parent) ?? [])].sort((x, y) =>
          depth === 0 ? Number(y.status === 'running') - Number(x.status === 'running') || y.startedAt - x.startedAt : x.startedAt - y.startedAt,
        )
        for (const a of list) {
          ordered.push({ a, depth })
          if (a.agentId !== undefined) walk(a.agentId, depth + 1)
        }
      }
      walk(undefined, 0)

      return (
        <Box flexDirection="column" gap={1}>
          <Text>
            <Text bold>{runningAgents} running</Text>
            <Text dimColor> · {agentList.length - runningAgents} finished</Text>
          </Text>
          {ordered.map(({ a, depth }) => {
            const clockText = formatClock((a.endedAt ?? at) - a.startedAt)
            const latest = a.trace[a.trace.length - 1]
            const line =
              a.status === 'running'
                ? latest?.summary ?? 'starting…'
                : a.answer ? oneLine(plainText(a.answer)) : ''
            const meta = [
              a.model?.replace(/^claude-/, ''),
              `${formatTokens(a.tokensIn)} in · ${formatTokens(a.tokensOut)} out`,
              a.isBackground ? 'background' : undefined,
            ].filter(Boolean).join(' · ')
            const title = agentLabel(a)
            const isRowOpen = isOpenRow.has(a.id)
            const glyph = AGENT_GLYPH[a.status]

            const head = Svg !== undefined ? (
              <Svg
                key={`card-${a.id}`}
                source={agentCardSvg({ width, type: a.type, status: a.status, depth, title, clock: clockText, description: a.description, meta, line })}
                alt={`${title}: ${a.description}, ${a.status}, ${clockText}`}
                width={width}
                height={AGENT_CARD_HEIGHT}
              />
            ) : (
              <Box key={`head-${a.id}`} flexDirection="column" marginLeft={depth * 2}>
                <Text wrap="truncate-end">
                  <Text color={glyph.color}>{glyph.glyph}</Text> <Text bold>{title}</Text>
                  <Text dimColor> {clockText}</Text>
                </Text>
                <Text wrap="truncate-end">{a.description}</Text>
                <Text dimColor wrap="truncate-end">{meta}</Text>
              </Box>
            )

            return (
              <Box key={`agent-${a.id}`} flexDirection="column">
                {head}
                <Box marginLeft={depth * 2} flexDirection="row">
                  <Button
                    key={`more-${a.id}`}
                    plain
                    dimColor={!isRowOpen}
                    label={isRowOpen ? '▾ Hide details' : `▸ Prompt, ${a.trace.length}-step trace${a.answer ? ' and answer' : ''}`}
                    onPress={() => toggle(a.id)}
                  />
                  <Box flexGrow={1} />
                  {askButton(a.id)}
                </Box>
                {isRowOpen && (
                  <Box flexDirection="column" borderStyle="round" paddingX={1} marginLeft={depth * 2} gap={1}>
                    <Box flexDirection="column">
                      <Text bold>Prompt</Text>
                      <Markdown text={a.prompt || '—'} dimColor />
                    </Box>
                    <Box flexDirection="column">
                      <Text>
                        <Text bold>Trace</Text>
                        <Text dimColor> · {a.toolCalls} tool {a.toolCalls === 1 ? 'call' : 'calls'}</Text>
                      </Text>
                      {a.trace.length === 0 && <Text dimColor>No tool calls yet.</Text>}
                      {a.trace.map(s => (
                        <Text key={`step-${a.id}-${s.id}`} wrap="truncate-end">
                          <Text color={CALL_GLYPH[s.status].color}>{CALL_GLYPH[s.status].glyph}</Text>
                          <Text dimColor> {formatClock(s.at - a.startedAt)} </Text>
                          {s.summary}
                        </Text>
                      ))}
                      {a.toolCalls > a.trace.length && <Text dimColor>… {a.toolCalls - a.trace.length} earlier calls</Text>}
                    </Box>
                    {a.answer && (
                      <Box flexDirection="column">
                        <Text bold color={a.status === 'failed' ? 'error' : undefined}>{a.status === 'failed' ? 'Error' : 'Answer'}</Text>
                        <Markdown text={a.answer} />
                      </Box>
                    )}
                  </Box>
                )}
              </Box>
            )
          })}
        </Box>
      )
    }

    // ── Shell ───────────────────────────────────────────────────────────────
    const shellTab = () => {
      if (shellList.length === 0) return <Text dimColor>No shell commands yet.</Text>
      return (
        <Box flexDirection="column">
          <Text>
            <Text bold>{shellList.length} commands</Text>
            <Text dimColor> · </Text>
            <Text color={runningShell > 0 ? 'warning' : undefined} dimColor={runningShell === 0}>{runningShell} running</Text>
            <Text dimColor> · </Text>
            <Text color={failedShell > 0 ? 'error' : undefined} dimColor={failedShell === 0}>{failedShell} failed</Text>
          </Text>
          {[...shellList].reverse().map(r => {
            const g = CALL_GLYPH[r.status]
            const duration = formatDuration(r.endedAt === undefined ? at - r.startedAt : r.endedAt - r.startedAt)
            const owner = r.agentId !== undefined ? agentById.get(r.agentId) : undefined
            const isRowOpen = isOpenRow.has(r.id)
            const label = r.description || oneLine(r.command)
            return (
              <Box key={`sh-${r.id}`} flexDirection="column" marginTop={1}>
                <Box flexDirection="row">
                  <Text color={g.color}>{g.glyph} </Text>
                  <Button key={`shb-${r.id}`} plain label={`${isRowOpen ? '▾' : '▸'} ${cut(label, Math.max(12, columns - 20))}`} onPress={() => toggle(r.id)} />
                  <Box flexGrow={1} />
                  <Text dimColor={r.status === 'ok'} color={r.status === 'running' ? 'warning' : undefined}>{duration} </Text>
                  {askButton(r.id)}
                </Box>
                <Box marginLeft={2}>
                  <Text dimColor wrap="truncate-end">
                    <Text color="bashBorder">❯</Text> {oneLine(r.command)}
                    {owner ? <Text color="claude">  ↳ {agentLabel(owner)}</Text> : ''}
                  </Text>
                </Box>
                {r.note && !isRowOpen && (
                  <Box marginLeft={2}>
                    <Text color={g.color} wrap="truncate-end">{r.note}</Text>
                  </Box>
                )}
                {isRowOpen && (
                  <Box flexDirection="column" marginLeft={2} marginTop={1} gap={1}>
                    <Code source={r.command} language="bash" wrap="wrap" />
                    {r.note && <Text color={g.color}>{g.glyph} {r.note}</Text>}
                    {r.stdout && (
                      <Box flexDirection="column">
                        <Text dimColor>stdout</Text>
                        <Code source={r.stdout} language="text" wrap="wrap" />
                      </Box>
                    )}
                    {r.stderr && (
                      <Box flexDirection="column">
                        <Text color={r.status === 'error' ? 'error' : 'warning'}>stderr</Text>
                        <Code source={r.stderr} language="text" wrap="wrap" />
                      </Box>
                    )}
                    {!r.stdout && !r.stderr && r.status !== 'running' && <Text dimColor>No output.</Text>}
                    <Text dimColor>
                      started {formatClock(r.startedAt - (callList[0]?.startedAt ?? r.startedAt))} into the session · {r.status}
                    </Text>
                  </Box>
                )}
              </Box>
            )
          })}
        </Box>
      )
    }

    // ── Files ───────────────────────────────────────────────────────────────
    const filesTab = () => {
      if (fileList.length === 0) return <Text dimColor>No files read or edited yet.</Text>
      const sorted = [...fileList].sort((x, y) => y.edits - x.edits || y.lastAt - x.lastAt)
      const edited = fileList.filter(f => f.edits > 0).length
      return (
        <Box flexDirection="column">
          <Text>
            <Text bold>{edited} edited</Text>
            <Text dimColor> · {fileList.length - edited} only read</Text>
          </Text>
          {sorted.map(f => {
            const dir = f.path.slice(0, f.path.length - baseName(f.path).length)
            return (
              <Box key={`file-${f.path}`} flexDirection="row">
                <Text wrap="truncate-start">
                  <Text dimColor>{oneLine(dir)}</Text>
                  <Text bold={f.edits > 0}>{oneLine(baseName(f.path))}</Text>
                </Text>
                <Box flexGrow={1} />
                <Text>
                  {f.edits > 0 ? <Text color="autoAccept">{` ✎ ${f.edits}`}</Text> : ''}
                  {f.reads > 0 ? <Text color="suggestion" dimColor>{` ▤ ${f.reads}`}</Text> : ''}
                </Text>
              </Box>
            )
          })}
        </Box>
      )
    }

    const body =
      current === 'subagents' ? subagents() : current === 'shell' ? shellTab() : current === 'files' ? filesTab() : overview()

    return (
      <Box flexDirection="column" gap={1} width={columns}>
        <Box flexDirection="column">
          {tabBar}
          {rule('tabs')}
        </Box>
        {body}
      </Box>
    )
  })
}

// Opens the panel on a tab, and on one row of it with its details open.
async function showInPanel($: EngineInterface, next: Tab, id?: string): Promise<void> {
  await update($, tab, () => next)
  if (id !== undefined) await update($, expanded, ids => (ids.includes(id) ? ids : [...ids, id]))
  await $.ui.open({ id: PANE, title: TITLE })
  const to = id === undefined ? ('start' as const) : { key: next === 'shell' ? `sh-${id}` : `agent-${id}` }
  await $.ui.scroll({ in: PANE, to, block: 'start' }).catch(() => undefined)
}

async function reset($: StateDollar): Promise<void> {
  await Promise.all([
    update($, calls, () => []),
    update($, shell, () => []),
    update($, agents, () => []),
    update($, files, () => []),
    update($, usage, () => ({ tokensIn: 0, tokensOut: 0, turns: 0 })),
    update($, expanded, () => []),
    update($, asked, () => []),
  ])
  isLive = false
}
