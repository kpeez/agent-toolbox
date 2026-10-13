// The panel's state and the one pure function that changes it. Handlers in
// register.tsx observe the engine (clock, tool results) and turn what they saw
// into a SessionEvent; `step` decides what that event does to the state. No
// clock, randomness or engine call happens here, so a list of events replays
// to the same state every time.

import type { AgentRun, AgentStatus, CallStatus, FileTouch, Session, ShellRun, ShellStatus, Tab, TraceStep } from '../types'
import type { Demo } from './demo'
import { baseName, clean, cut, oneLine, tail } from './text'

export const KEEP_CALLS = 1500
export const KEEP_SHELL = 150
export const KEEP_AGENTS = 60
export const KEEP_TRACE = 40
export const KEEP_FILES = 300
const STDOUT_CHARS = 4000
const STDERR_CHARS = 2000
const PROMPT_CHARS = 4000
const ANSWER_CHARS = 8000

export const SHELL_TOOLS = new Set(['Bash', 'PowerShell'])
const READ_TOOLS = new Set(['Read', 'NotebookRead'])
const EDIT_TOOLS = new Set(['Edit', 'MultiEdit', 'Write', 'NotebookEdit'])

// The first of these input fields that holds a string names the call.
const SUMMARY_FIELDS = [
  'description', 'command', 'file_path', 'notebook_path', 'pattern', 'url',
  'query', 'skill', 'path', 'prompt',
]
const PATH_FIELDS = new Set(['file_path', 'notebook_path', 'path'])

function summarize(tool: string, input: Record<string, unknown>): string {
  const name = tool.replace(/^mcp__/, '').replace(/__/g, ' ')
  for (const field of SUMMARY_FIELDS) {
    const value = input[field]
    if (typeof value !== 'string' || value.length === 0) continue
    return oneLine(`${name} ${PATH_FIELDS.has(field) ? baseName(value) : value}`)
  }
  return name
}

export type SessionEvent =
  | {
      type: 'AgentSpawned'; at: number; id: string; agentId?: string; parentAgentId?: string
      agentType: string; name?: string; description: string; prompt: string; model?: string; isBackground: boolean
    }
  | { type: 'ToolStarted'; at: number; id: string; tool: string; agentId?: string; input: Record<string, unknown> }
  | {
      type: 'ToolFinished'; at: number; id: string; tool: string; agentId?: string; status: CallStatus
      /** The file the call named, when it named one. */
      path?: string
      /** What a shell call returned; ignored for other tools. */
      shell?: { stdout: string; stderr: string; note?: string; isBackground: boolean }
    }
  | {
      type: 'TurnCompleted'; at: number; agentId?: string; reason: string
      tokensIn: number; tokensOut: number; model?: string; answer?: string
    }
  /** The person sent a prompt that is not a slash command. */
  | { type: 'PromptSubmitted'; at: number }
  /** The asked rows rode a prompt. */
  | { type: 'AsksSent' }
  | { type: 'AskToggled'; id: string }
  | { type: 'RowToggled'; id: string }
  | { type: 'TabShown'; tab: Tab; id?: string }
  | { type: 'DemoLoaded'; sample: Demo }
  | { type: 'Cleared' }

export const emptySession = (): Session => ({
  calls: [], shell: [], agents: [], files: [],
  usage: { tokensIn: 0, tokensOut: 0, turns: 0 },
  tab: 'overview', expanded: [], asked: [], turnFrom: 0,
})

const toggle = (ids: string[], id: string): string[] => (ids.includes(id) ? ids.filter(one => one !== id) : [...ids, id])

export function step(s: Session, e: SessionEvent): Session {
  switch (e.type) {
    case 'AgentSpawned': {
      const run: AgentRun = {
        id: e.id, agentId: e.agentId, parentAgentId: e.parentAgentId, type: e.agentType, name: e.name,
        description: oneLine(e.description), prompt: cut(clean(e.prompt), PROMPT_CHARS), model: e.model,
        isBackground: e.isBackground, status: 'running', startedAt: e.at, toolCalls: 0, trace: [], tokensIn: 0, tokensOut: 0,
      }
      return { ...s, agents: [...s.agents.filter(a => a.id !== run.id), run].slice(-KEEP_AGENTS) }
    }

    case 'ToolStarted': {
      const calls = [...s.calls, { id: e.id, tool: e.tool, agentId: e.agentId, status: 'running' as const, startedAt: e.at }].slice(-KEEP_CALLS)
      const shell = !SHELL_TOOLS.has(e.tool) ? s.shell : [...s.shell, {
        id: e.id, agentId: e.agentId, status: 'running' as const, startedAt: e.at, stdout: '', stderr: '',
        command: clean(String(e.input.command ?? '')), description: oneLine(String(e.input.description ?? '')),
      } satisfies ShellRun].slice(-KEEP_SHELL)
      const traced: TraceStep = { id: e.id, tool: e.tool, summary: summarize(e.tool, e.input), status: 'running', at: e.at }
      const agents = e.agentId === undefined ? s.agents : s.agents.map(a =>
        a.agentId === e.agentId
          ? { ...a, status: 'running' as const, endedAt: undefined, toolCalls: a.toolCalls + 1, trace: [...a.trace, traced].slice(-KEEP_TRACE) }
          : a,
      )
      return { ...s, calls, shell, agents }
    }

    case 'ToolFinished': {
      const { id, status } = e
      const calls = s.calls.map(c => (c.id === id ? { ...c, status, endedAt: e.at } : c))
      const agents = e.agentId === undefined ? s.agents : s.agents.map(a =>
        a.agentId === e.agentId ? { ...a, trace: a.trace.map(t => (t.id === id ? { ...t, status } : t)) } : a,
      )
      const out = e.shell
      const shell = !SHELL_TOOLS.has(e.tool) || out === undefined ? s.shell : s.shell.map(r =>
        r.id === id
          ? {
              ...r, endedAt: e.at, status: (out.isBackground && status === 'ok' ? 'background' : status) as ShellStatus,
              stdout: tail(clean(out.stdout), STDOUT_CHARS), stderr: tail(clean(out.stderr), STDERR_CHARS),
              note: out.note === undefined ? undefined : oneLine(out.note),
            }
          : r,
      )
      const isEdit = EDIT_TOOLS.has(e.tool)
      const touches = status === 'ok' && e.path !== undefined && (isEdit || READ_TOOLS.has(e.tool))
      const files = !touches ? s.files : (() => {
        const old = s.files.find(f => f.path === e.path)
        const touch: FileTouch = {
          path: e.path as string,
          reads: (old?.reads ?? 0) + (isEdit ? 0 : 1),
          edits: (old?.edits ?? 0) + (isEdit ? 1 : 0),
          lastAt: e.at,
        }
        return [...s.files.filter(f => f.path !== e.path), touch].slice(-KEEP_FILES)
      })()
      return { ...s, calls, agents, shell, files }
    }

    case 'TurnCompleted': {
      const usage = {
        tokensIn: s.usage.tokensIn + e.tokensIn,
        tokensOut: s.usage.tokensOut + e.tokensOut,
        turns: s.usage.turns + (e.agentId === undefined ? 1 : 0),
      }
      if (e.agentId === undefined) return { ...s, usage }
      const status: AgentStatus = e.reason === 'answer' ? 'done' : e.reason === 'aborted' ? 'stopped' : 'failed'
      const agents = s.agents.map(a =>
        a.agentId === e.agentId
          ? {
              ...a, status, endedAt: e.at, model: e.model ?? a.model,
              answer: e.answer ? cut(clean(e.answer), ANSWER_CHARS) : a.answer,
              tokensIn: a.tokensIn + e.tokensIn, tokensOut: a.tokensOut + e.tokensOut,
            }
          : a,
      )
      return { ...s, usage, agents }
    }

    case 'PromptSubmitted':
      return { ...s, turnFrom: e.at }
    case 'AsksSent':
      return { ...s, asked: [] }
    case 'AskToggled':
      return { ...s, asked: toggle(s.asked, e.id) }
    case 'RowToggled':
      return { ...s, expanded: toggle(s.expanded, e.id) }
    case 'TabShown':
      return { ...s, tab: e.tab, expanded: e.id === undefined || s.expanded.includes(e.id) ? s.expanded : [...s.expanded, e.id] }
    case 'DemoLoaded':
      return { ...s, ...e.sample, turnFrom: 0 }
    case 'Cleared':
      return { ...emptySession(), tab: s.tab, turnFrom: s.turnFrom }
  }
}

/** Whether anything still runs, so the clock ticks only while it matters. */
export const isLive = (s: Session): boolean =>
  s.shell.some(r => r.status === 'running') || s.agents.some(a => a.status === 'running')
