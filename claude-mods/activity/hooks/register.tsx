import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Call, CallField, CallStatus } from '../types'

const PANE = 'activity'
const KEEP = 500
const FIELD_CHARS = 600
const REASON_CHARS = 300
const calls = atom({ plugin: 'activity', key: 'calls' } as const, [])
const expanded = atom({ plugin: 'activity', key: 'expanded' } as const, [])

// The first of these input fields that holds a string names the call.
const SUMMARY_FIELDS = [
  'command', 'file_path', 'notebook_path', 'pattern', 'url', 'query',
  'skill', 'description', 'prompt', 'path',
]
// Envelope keys the engine adds beside a tool's own arguments.
const ENVELOPE = new Set(['tool', 'tool_use_id', 'agentId', 'consent'])

// Colors are theme keys, so the pane follows the person's theme.
const STATUS: Record<CallStatus, { glyph: string; color: string }> = {
  running: { glyph: '◌', color: 'warning' },
  ok: { glyph: '✓', color: 'success' },
  error: { glyph: '✗', color: 'error' },
  denied: { glyph: '⊘', color: 'warning' },
}

const KINDS: { match: RegExp; icon: string; color: string }[] = [
  { match: /^Bash$|^PowerShell$/, icon: '❯', color: 'bashBorder' },
  { match: /^(Read|NotebookRead)$/, icon: '▤', color: 'suggestion' },
  { match: /^(Edit|MultiEdit|Write|NotebookEdit)$/, icon: '✎', color: 'autoAccept' },
  { match: /^(Grep|Glob|LS)$/, icon: '⌕', color: 'ide' },
  { match: /^Web/, icon: '◍', color: 'planMode' },
  { match: /^(Agent|Task)$/, icon: '✦', color: 'claude' },
  { match: /^Skill$/, icon: '◆', color: 'remember' },
  { match: /^mcp__/, icon: '⧉', color: 'merged' },
]
const OTHER = { icon: '•', color: 'subtle' }

const kindOf = (tool: string) => KINDS.find(k => k.match.test(tool)) ?? OTHER

const toolName = (tool: string): string => tool.replace(/^mcp__/, '').replace(/__/g, ' ')

const cut = (s: string, max: number): string => (s.length > max ? `${s.slice(0, max - 1)}…` : s)

function summarize(input: Record<string, unknown>): string {
  for (const field of SUMMARY_FIELDS) {
    const value = input[field]
    if (typeof value === 'string' && value.length > 0) {
      return value.replace(/\s+/g, ' ').trim()
    }
  }
  return ''
}

// The call's own arguments, as the expanded row shows them.
function fieldsOf(input: Record<string, unknown>): CallField[] {
  return Object.entries(input)
    .filter(([key, value]) => !ENVELOPE.has(key) && value !== undefined && value !== '')
    .map(([key, value]) => ({
      key,
      value: cut(typeof value === 'string' ? value : JSON.stringify(value), FIELD_CHARS),
    }))
}

function formatDuration(ms: number | undefined): string {
  if (ms === undefined) return '…'.padStart(6)
  if (ms < 1000) return `${ms}ms`.padStart(6)
  if (ms < 59_950) return `${(ms / 1000).toFixed(1)}s`.padStart(6)
  const seconds = Math.round(ms / 1000)
  return `${Math.floor(seconds / 60)}m${seconds % 60}s`.padStart(6)
}

// Slow calls stand out; quick ones recede.
const durationColor = (ms: number | undefined): string | undefined =>
  ms === undefined ? undefined : ms >= 30_000 ? 'warning' : undefined

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'activity',
      description: 'Show the tool calls of this session in a pane',
    })
    return next(e)
  })

  on('command.run', { command: 'activity' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Activity' })
    return { text: 'Activity pane opened.' }
  })

  on('tool.call', async ($, e, next) => {
    const startedAt = await $.clock.now()
    const input = e as unknown as Record<string, unknown>
    const call: Call = {
      id: e.tool_use_id ?? `${e.tool}-${startedAt}-${Math.random()}`,
      tool: String(e.tool),
      summary: summarize(input),
      fields: fieldsOf(input),
      isSubagent: e.agentId !== undefined,
      startedAt,
      status: 'running',
    }
    await update($, calls, list => [...list, call].slice(-KEEP))

    const ran = await next(e)

    const durationMs = (await $.clock.now()) - startedAt
    const status: CallStatus =
      ran.deny !== undefined ? 'denied' : ran.isError === true ? 'error' : 'ok'
    const why = ran.deny ?? (ran.isError === true ? ran.text : undefined)
    const reason = why ? cut(why.replace(/\s+/g, ' ').trim(), REASON_CHARS) : undefined
    await update($, calls, list =>
      list.map(one => (one.id === call.id ? { ...one, durationMs, status, reason } : one)),
    )
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const list = await read($, calls)
    const open = new Set(await read($, expanded))
    const failed = list.filter(c => c.status === 'error' || c.status === 'denied').length
    const running = list.filter(c => c.status === 'running').length
    const columns = e.props.bodyColumns

    const toggle = (id: string) =>
      update($, expanded, ids => (ids.includes(id) ? ids.filter(one => one !== id) : [...ids, id]))

    const row = (call: Call) => {
      const kind = kindOf(call.tool)
      const status = STATUS[call.status]
      const name = toolName(call.tool)
      const isOpen = open.has(call.id)
      // Status, duration, icon and tool name, then the summary in what is left.
      const prefix = 1 + 1 + 6 + 1 + 1 + 1 + name.length + (call.isSubagent ? 2 : 0) + 1 + 2
      const label = cut(call.summary || name, Math.max(8, columns - prefix))
      return (
        <Box key={`row-${call.id}`} flexDirection="column">
          <Box flexDirection="row">
            <Text wrap="truncate-end">
              <Text color={status.color}>{status.glyph}</Text>{' '}
              <Text color={durationColor(call.durationMs)} dimColor={call.status === 'ok'}>
                {formatDuration(call.durationMs)}
              </Text>{' '}
              <Text color={kind.color}>{kind.icon}</Text>{' '}
              <Text bold>{name}</Text>
              {call.isSubagent ? <Text color="claude"> ↳</Text> : ''}{' '}
            </Text>
            <Button key={`call-${call.id}`} plain dimColor={!isOpen} label={`${isOpen ? '▾' : '▸'} ${label}`} onPress={() => toggle(call.id)} />
          </Box>
          {isOpen && (
            <Box flexDirection="column" borderStyle="round" borderColor={kind.color} paddingX={1} marginLeft={2}>
              {call.fields.map(field => (
                <Text wrap="wrap">
                  <Text color={kind.color}>{field.key}</Text> {field.value}
                </Text>
              ))}
              {call.reason !== undefined && (
                <Text color={status.color} wrap="wrap">
                  {status.glyph} {call.reason}
                </Text>
              )}
              <Text dimColor>
                {call.status} · {formatDuration(call.durationMs).trim()}
                {call.isSubagent ? ' · in a subagent' : ''}
              </Text>
            </Box>
          )}
        </Box>
      )
    }

    return (
      <Box flexDirection="column" width={columns}>
        <Text>
          <Text bold>{list.length} calls</Text>
          <Text dimColor> · </Text>
          <Text color={running > 0 ? 'warning' : undefined} dimColor={running === 0}>{running} running</Text>
          <Text dimColor> · </Text>
          <Text color={failed > 0 ? 'error' : undefined} dimColor={failed === 0}>{failed} failed</Text>
        </Text>
        {list.length === 0 ? (
          <Text dimColor>No tool calls yet.</Text>
        ) : (
          <Text dimColor>Click a call to see its full input.</Text>
        )}
        {[...list].reverse().map(row)}
      </Box>
    )
  })
}
