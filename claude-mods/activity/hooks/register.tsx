import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Call, CallStatus } from '../types'

const PANE = 'activity'
const KEEP = 500
const calls = atom({ plugin: 'activity', key: 'calls' } as const, [])

// The first of these input fields that holds a string names the call.
const SUMMARY_FIELDS = [
  'command', 'file_path', 'notebook_path', 'pattern', 'url', 'query',
  'skill', 'description', 'prompt', 'path',
]

const GLYPH: Record<CallStatus, string> = {
  running: '…', ok: '✓', error: '✗', denied: '⊘',
}

function summarize(input: Record<string, unknown>): string {
  for (const field of SUMMARY_FIELDS) {
    const value = input[field]
    if (typeof value === 'string' && value.length > 0) {
      return value.replace(/\s+/g, ' ').trim()
    }
  }
  return ''
}

function formatDuration(ms: number | undefined): string {
  if (ms === undefined) return '…'.padStart(6)
  if (ms < 1000) return `${ms}ms`.padStart(6)
  if (ms < 59_950) return `${(ms / 1000).toFixed(1)}s`.padStart(6)
  const seconds = Math.round(ms / 1000)
  return `${Math.floor(seconds / 60)}m${seconds % 60}s`.padStart(6)
}

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
    const call: Call = {
      id: e.tool_use_id ?? `${e.tool}-${startedAt}-${Math.random()}`,
      tool: String(e.tool),
      summary: summarize(e as unknown as Record<string, unknown>),
      isSubagent: e.agentId !== undefined,
      startedAt,
      status: 'running',
    }
    await update($, calls, list => [...list, call].slice(-KEEP))

    const ran = await next(e)

    const durationMs = (await $.clock.now()) - startedAt
    const status: CallStatus =
      ran.deny !== undefined ? 'denied' : ran.isError === true ? 'error' : 'ok'
    await update($, calls, list =>
      list.map(one => (one.id === call.id ? { ...one, durationMs, status } : one)),
    )
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, calls)
    const failed = list.filter(c => c.status === 'error' || c.status === 'denied').length
    const running = list.filter(c => c.status === 'running').length

    return (
      <Box flexDirection="column" width={e.props.bodyColumns}>
        <Text bold>
          {list.length} calls · {running} running · {failed} failed
        </Text>
        {list.length === 0 && <Text dimColor>No tool calls yet.</Text>}
        {[...list].reverse().map(call => (
          <Text
            wrap="truncate-end"
            color={call.status === 'ok' || call.status === 'running' ? undefined : 'red'}
            dimColor={call.status === 'ok'}
          >
            {GLYPH[call.status]} {formatDuration(call.durationMs)} {call.isSubagent ? '↳ ' : ''}
            {call.tool} {call.summary}
          </Text>
        ))}
      </Box>
    )
  })
}
