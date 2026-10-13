// A short session as the events `step` sees, and the trace it folds into.
// From claude-mods/session-panel, rewrite the checked-in trace with
//   bun tests/trace.ts --write
// and confirm it matches `step` (exit 1 when stale) with
//   bun tests/trace.ts --check
// The mod test harness loads only code files, so this check runs outside it.
// Open that file in plugins/swe/skills/reducer/assets/flow-viewer.html to step through it.

import { emptySession, step } from '../hooks/session'
import type { SessionEvent } from '../hooks/session'

const T = 1_700_000_000_000

export const EVENTS: SessionEvent[] = [
  { type: 'PromptSubmitted', at: T },
  { type: 'ToolStarted', at: T + 1000, id: 'read-1', tool: 'Read', input: { file_path: '/repo/src/app.ts' } },
  { type: 'ToolFinished', at: T + 1200, id: 'read-1', tool: 'Read', status: 'ok', path: '/repo/src/app.ts' },
  {
    type: 'AgentSpawned', at: T + 2000, id: 'agent-1', agentId: 'agent-1', agentType: 'Explore',
    description: 'Find the config loader', prompt: 'Where is config loaded?', isBackground: false,
  },
  { type: 'ToolStarted', at: T + 2500, id: 'grep-1', tool: 'Grep', agentId: 'agent-1', input: { pattern: 'loadConfig' } },
  { type: 'ToolStarted', at: T + 3000, id: 'bash-1', tool: 'Bash', input: { command: 'npm test', description: 'Run tests' } },
  { type: 'ToolFinished', at: T + 3400, id: 'grep-1', tool: 'Grep', agentId: 'agent-1', status: 'ok' },
  {
    type: 'TurnCompleted', at: T + 4000, agentId: 'agent-1', reason: 'answer',
    tokensIn: 1200, tokensOut: 300, answer: 'Config loads in src/config.ts.',
  },
  {
    type: 'ToolFinished', at: T + 6000, id: 'bash-1', tool: 'Bash', status: 'error',
    shell: { stdout: '1 failing', stderr: 'AssertionError: expected 2', isBackground: false },
  },
  { type: 'AskToggled', id: 'bash-1' },
  { type: 'TabShown', tab: 'shell', id: 'bash-1' },
  { type: 'PromptSubmitted', at: T + 9000 },
  { type: 'AsksSent' },
  { type: 'TurnCompleted', at: T + 12000, reason: 'answer', tokensIn: 5000, tokensOut: 800 },
]

/** One JSON line per event: the state before it, the event, the state after. */
export function traceLines(events: SessionEvent[]): string {
  let state = emptySession()
  return events.map((event, i) => {
    const before = state
    state = step(state, event)
    return JSON.stringify({ i, event, before, after: state })
  }).join('\n') + '\n'
}

if (import.meta.main) {
  const file = Bun.file(new URL('./fixtures/trace.jsonl', import.meta.url))
  const fresh = traceLines(EVENTS)
  if (process.argv.includes('--write')) await Bun.write(file, fresh)
  else if (process.argv.includes('--check')) {
    if ((await file.text()) !== fresh) {
      console.error('tests/fixtures/trace.jsonl is stale: run `bun tests/trace.ts --write`')
      process.exit(1)
    }
  } else process.stdout.write(fresh)
}
