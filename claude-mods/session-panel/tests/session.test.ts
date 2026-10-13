import { expect, test } from 'claude-code/testing'

import { emptySession, step } from '../hooks/session'
import type { SessionEvent } from '../hooks/session'
import type { CallStatus, Session } from '../types'

// A small seeded generator (mulberry32), so a failing seed replays exactly.
function rng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const TOOLS = ['Bash', 'PowerShell', 'Read', 'Edit', 'Grep', 'WebFetch']
const STATUSES: CallStatus[] = ['ok', 'error', 'denied']
const REASONS = ['answer', 'aborted', 'error']

// Random interleavings of what the engine reports, then the close of every
// started call and every agent's last turn, in random order.
function session(seed: number, length: number): SessionEvent[] {
  const r = rng(seed)
  const pick = <T,>(xs: T[]): T => xs[Math.floor(r() * xs.length)] as T
  const open = new Map<string, { tool: string; agentId?: string }>()
  const agents: string[] = []
  const events: SessionEvent[] = []
  let at = 0
  let n = 0
  const finish = (id: string) => {
    const call = open.get(id)!
    open.delete(id)
    events.push({
      type: 'ToolFinished', at: (at += 10), id, tool: call.tool, agentId: call.agentId, status: pick(STATUSES),
      path: '/repo/a.ts', shell: { stdout: 'out', stderr: '', isBackground: r() < 0.2 },
    })
  }
  for (let i = 0; i < length; i++) {
    const roll = r()
    if (roll < 0.1) {
      const id = `agent-${n++}`
      agents.push(id)
      events.push({ type: 'AgentSpawned', at: (at += 10), id, agentId: id, agentType: 'Explore', description: 'd', prompt: 'p', isBackground: r() < 0.3 })
    } else if (roll < 0.5) {
      const id = `call-${n++}`
      const tool = pick(TOOLS)
      const agentId = agents.length > 0 && r() < 0.5 ? pick(agents) : undefined
      open.set(id, { tool, agentId })
      events.push({ type: 'ToolStarted', at: (at += 10), id, tool, agentId, input: { command: 'ls', file_path: '/repo/a.ts' } })
    } else if (roll < 0.8 && open.size > 0) {
      finish(pick([...open.keys()]))
    } else if (roll < 0.9 && agents.length > 0) {
      events.push({ type: 'TurnCompleted', at: (at += 10), agentId: pick(agents), reason: pick(REASONS), tokensIn: 5, tokensOut: 1 })
    } else {
      events.push(pick<SessionEvent>([
        { type: 'TurnCompleted', at: (at += 10), reason: 'answer', tokensIn: 5, tokensOut: 1 },
        { type: 'PromptSubmitted', at: (at += 10) },
        { type: 'TabShown', tab: 'shell' },
      ]))
    }
  }
  while (open.size > 0) finish(pick([...open.keys()]))
  for (const agentId of agents.sort(() => r() - 0.5)) {
    events.push({ type: 'TurnCompleted', at: (at += 10), agentId, reason: pick(REASONS), tokensIn: 1, tokensOut: 1 })
  }
  return events
}

const running = (s: Session): string[] => [
  ...s.calls.filter(c => c.status === 'running').map(c => `call ${c.id}`),
  ...s.shell.filter(c => c.status === 'running').map(c => `shell ${c.id}`),
  ...s.agents.filter(a => a.status === 'running').map(a => `agent ${a.id}`),
  ...s.agents.flatMap(a => a.trace.filter(t => t.status === 'running').map(t => `trace ${a.id}/${t.id}`)),
]

test('once every started call and agent turn has ended, nothing shows as running', () => {
  for (let seed = 1; seed <= 300; seed++) {
    const length = seed % 50 === 0 ? 2500 : 1 + (seed % 80)
    const end = session(seed, length).reduce(step, emptySession())
    expect({ seed, running: running(end) }).toEqual({ seed, running: [] })
  }
})
