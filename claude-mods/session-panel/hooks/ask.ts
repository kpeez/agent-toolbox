// What an "ask" attaches to the next prompt: one context block per item the
// person armed in the panel, read by the model and never shown to them.

import type { AgentRun, ShellRun } from '../types'
import { formatDuration } from './text'

const fence = (body: string): string => {
  const longest = Math.max(2, ...[...body.matchAll(/`+/g)].map(m => m[0].length))
  const marks = '`'.repeat(longest + 1)
  return `${marks}\n${body}\n${marks}`
}

export function shellAskText(r: ShellRun): string {
  const duration = r.endedAt === undefined ? 'still running' : formatDuration(r.endedAt - r.startedAt)
  return [
    'The user attached this shell command from the session panel to ask about it.',
    r.description ? `Description: ${r.description}` : undefined,
    `Status: ${r.status}${r.note ? ` (${r.note})` : ''} · ${duration}`,
    'Command:',
    fence(r.command),
    r.stdout ? `stdout (its end):\n${fence(r.stdout)}` : undefined,
    r.stderr ? `stderr (its end):\n${fence(r.stderr)}` : undefined,
  ].filter(line => line !== undefined).join('\n')
}

export function agentAskText(a: AgentRun): string {
  const duration = a.endedAt === undefined ? 'still running' : formatDuration(a.endedAt - a.startedAt)
  const steps = a.trace.map(s => `- ${s.status} ${s.summary}`).join('\n')
  return [
    'The user attached this subagent run from the session panel to ask about it.',
    `Agent: ${a.name ? `${a.name} (${a.type})` : a.type}${a.model ? ` on ${a.model}` : ''}`,
    `Task: ${a.description}`,
    `Status: ${a.status} · ${duration} · ${a.toolCalls} tool calls`,
    `Prompt:\n${fence(a.prompt)}`,
    steps ? `Latest tool calls:\n${steps}` : undefined,
    a.answer ? `${a.status === 'failed' ? 'Error' : 'Answer'}:\n${fence(a.answer)}` : undefined,
  ].filter(line => line !== undefined).join('\n')
}
