// Made-up session data in every state the panel draws: running, done, failed,
// stopped and nested agents; shell commands that pass, fail with colored
// output, run in the background, are denied or still run. `/panel demo`
// loads it so the design can be judged without waiting for real work.

import type { AgentRun, CallMark, FileTouch, ShellRun, TraceStep, Usage } from '../types'
import { clean } from './text'

const SEC = 1000
const MIN = 60 * SEC

export type Demo = {
  calls: CallMark[]
  shell: ShellRun[]
  agents: AgentRun[]
  files: FileTouch[]
  usage: Usage
}

export function demo(now: number): Demo {
  const t0 = now - 14 * MIN
  const at = (offset: number) => t0 + offset

  const step = (id: string, tool: string, summary: string, offset: number, status: TraceStep['status'] = 'ok'): TraceStep => ({
    id, tool, summary, status, at: at(offset),
  })

  const agents: AgentRun[] = [
    {
      id: 'demo-explore', agentId: 'demo-explore', type: 'Explore', description: 'Map how panes render on desktop',
      prompt: 'Find where `ui.render` hooks for `Pane` are drawn on the **desktop** surface and list the elements available there. Medium breadth.',
      model: 'claude-haiku-5-5', isBackground: false, status: 'done', startedAt: at(1 * MIN), endedAt: at(3.4 * MIN),
      toolCalls: 9, tokensIn: 48_200, tokensOut: 2_140,
      trace: [
        step('e1', 'Grep', 'Grep ui.render', 1.1 * MIN),
        step('e2', 'Read', 'Read register.tsx', 1.4 * MIN),
        step('e3', 'Read', 'Read desktop.ts', 1.9 * MIN),
        step('e4', 'Glob', 'Glob **/*.d.ts', 2.6 * MIN),
      ],
      answer: '## Findings\n\n- Desktop panes draw `Box`, `Text`, `Button`, `Svg`, `Code` and `Markdown`.\n- `Svg` with `isInteractive` gets hover and `<title>` tooltips, but no script.\n- The subagents mod draws one SVG card per agent in `hooks/desktop.ts`.',
    },
    {
      id: 'demo-impl', agentId: 'demo-impl', type: 'swe:implementer', description: 'Add the shell tab with output tails',
      prompt: 'Implement the Shell tab: one row per Bash call, expandable to the command and the tails of stdout and stderr. Keep control characters out of every drawn string.',
      model: 'claude-sonnet-5-5', isBackground: false, status: 'running', startedAt: at(5 * MIN),
      toolCalls: 23, tokensIn: 131_000, tokensOut: 9_800,
      trace: [
        step('i1', 'Read', 'Read register.tsx', 5.2 * MIN),
        step('i2', 'Edit', 'Edit register.tsx', 7 * MIN),
        step('i3', 'Bash', 'Bash claude plugin test .', 8.5 * MIN, 'error'),
        step('i4', 'Edit', 'Edit text.ts', 10 * MIN),
        step('i5', 'Bash', 'Bash claude plugin test .', 12.8 * MIN, 'running'),
      ],
    },
    {
      id: 'demo-child', agentId: 'demo-child', parentAgentId: 'demo-impl', type: 'swe:explorer', name: 'ansi-scout',
      description: 'Find how other mods strip ANSI codes', prompt: 'Look for helpers that remove escape sequences from command output.',
      model: 'claude-haiku-5-5', isBackground: false, status: 'running', startedAt: at(9 * MIN),
      toolCalls: 6, tokensIn: 22_400, tokensOut: 610,
      trace: [step('c1', 'Grep', 'Grep \\x1b\\[', 9.3 * MIN), step('c2', 'Read', 'Read text.ts', 11 * MIN, 'running')],
    },
    {
      id: 'demo-review', agentId: 'demo-review', type: 'swe:reviewer', description: 'Review the timeline drawing for overflow',
      prompt: 'Review `timelineSvg` for spans that overflow the plot and for labels that collide at narrow widths.',
      model: 'claude-opus-5-5', isBackground: true, status: 'failed', startedAt: at(3.8 * MIN), endedAt: at(4.9 * MIN),
      toolCalls: 4, tokensIn: 30_100, tokensOut: 420,
      trace: [step('r1', 'Read', 'Read svg.ts', 4 * MIN), step('r2', 'Bash', 'Bash bun run lint', 4.6 * MIN, 'error')],
      answer: 'API error: the request timed out after 60s.',
    },
    {
      id: 'demo-stop', agentId: 'demo-stop', type: 'general-purpose', description: 'Survey pane designs in other tools',
      prompt: 'Collect three examples of dense activity timelines.', model: 'claude-sonnet-5-5', isBackground: false,
      status: 'stopped', startedAt: at(0.3 * MIN), endedAt: at(0.9 * MIN), toolCalls: 2, tokensIn: 8_000, tokensOut: 90,
      trace: [step('s1', 'WebSearch', 'WebSearch activity timeline UI', 0.5 * MIN)],
    },
  ]

  const red = '\x1b[31m'
  const green = '\x1b[32m'
  const dim = '\x1b[2m'
  const reset = '\x1b[0m'
  const raw: ShellRun[] = [
    {
      id: 'demo-sh-status', command: 'git status --short', description: 'Show working tree status', status: 'ok',
      startedAt: at(0.2 * MIN), endedAt: at(0.2 * MIN + 180), stdout: ' M hooks/register.tsx\n?? hooks/svg.ts\n?? hooks/demo.ts', stderr: '',
    },
    {
      id: 'demo-sh-test', command: 'claude plugin test ~/.claude/dev-mods/session-panel', description: 'Run the mod tests',
      agentId: 'demo-impl', status: 'error', startedAt: at(8.5 * MIN), endedAt: at(8.5 * MIN + 6_400),
      stdout: `${green}✓${reset} the pane follows a subagent from spawn to done ${dim}(41ms)${reset}\n${red}✗${reset} the shell tab keeps escape sequences out ${dim}(12ms)${reset}`,
      stderr: `${red}expected "␛[31mfail" not to contain "␛"${reset}\n    at shell.test.ts:42:5`,
      note: 'Exit code 1',
    },
    {
      id: 'demo-sh-dev', command: 'bun run dev --port 5173', description: 'Start the preview server', status: 'background',
      startedAt: at(2 * MIN), endedAt: at(2 * MIN + 900), stdout: '  VITE v6.2.0  ready in 412 ms\n\n  ➜  Local:   http://localhost:5173/', stderr: '',
      note: 'Running in the background',
    },
    {
      id: 'demo-sh-install', command: 'npm install --no-audit', description: 'Install package dependencies', status: 'ok',
      startedAt: at(1.2 * MIN), endedAt: at(1.2 * MIN + 41_000),
      stdout: 'added 412 packages in 41s\r\n\r[####################] 100%', stderr: 'npm warn deprecated inflight@1.0.6',
    },
    {
      id: 'demo-sh-rm', command: 'rm -rf node_modules/.cache', description: 'Delete the build cache', status: 'denied',
      startedAt: at(6 * MIN), endedAt: at(6 * MIN), stdout: '', stderr: '', note: 'The user declined this command.',
    },
    {
      id: 'demo-sh-run', command: 'claude plugin test ~/.claude/dev-mods/session-panel', description: 'Run the mod tests again',
      agentId: 'demo-impl', status: 'running', startedAt: at(12.8 * MIN), stdout: '', stderr: '',
    },
  ]

  // Stored as a real capture stores them: cleaned of escape sequences.
  const shell = raw.map(r => ({ ...r, stdout: clean(r.stdout), stderr: clean(r.stderr) }))

  // Main-loop tool calls spread over the session, plus each shell run and
  // each subagent step as a call of its own loop.
  const tools = ['Read', 'Grep', 'Edit', 'Read', 'Glob', 'Read', 'Edit', 'WebFetch', 'Skill', 'Read']
  const calls: CallMark[] = []
  for (let i = 0; i < 34; i++) {
    const startedAt = at(i * 24 * SEC + (i % 3) * 5 * SEC)
    if (startedAt > now) break
    calls.push({
      id: `demo-call-${i}`, tool: tools[i % tools.length] ?? 'Read', status: i === 17 ? 'error' : 'ok',
      startedAt, endedAt: startedAt + 300 + (i % 4) * 400,
    })
  }
  for (const run of shell) {
    calls.push({
      id: run.id, tool: 'Bash', agentId: run.agentId,
      status: run.status === 'background' ? 'ok' : run.status, startedAt: run.startedAt, endedAt: run.endedAt,
    })
  }
  for (const agent of agents) {
    for (const s of agent.trace) {
      calls.push({ id: `${agent.id}-${s.id}`, tool: s.tool, agentId: agent.agentId, status: s.status, startedAt: s.at, endedAt: s.status === 'running' ? undefined : s.at + 800 })
    }
  }
  calls.sort((a, b) => a.startedAt - b.startedAt)

  const files: FileTouch[] = [
    { path: '/Users/kyle/.claude/dev-mods/session-panel/hooks/register.tsx', reads: 4, edits: 6, lastAt: at(10 * MIN) },
    { path: '/Users/kyle/.claude/dev-mods/session-panel/hooks/svg.ts', reads: 2, edits: 3, lastAt: at(9 * MIN) },
    { path: '/Users/kyle/.claude/dev-mods/session-panel/hooks/text.ts', reads: 3, edits: 1, lastAt: at(11 * MIN) },
    { path: '/Users/kyle/code/agent-toolbox/claude-mods/subagents/hooks/desktop.ts', reads: 2, edits: 0, lastAt: at(1.9 * MIN) },
    { path: '/Users/kyle/code/agent-toolbox/AGENTS.md', reads: 1, edits: 0, lastAt: at(0.4 * MIN) },
  ]

  return { calls, shell, agents, files, usage: { tokensIn: 412_000, tokensOut: 31_500, turns: 7 } }
}
