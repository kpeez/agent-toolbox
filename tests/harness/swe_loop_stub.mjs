// Drive plugins/swe/workflows/swe-loop.js end to end with scripted agent
// results and no real agents, tracker, or git.
//
// The workflow file is a runtime *body*, not a module: it top-level-returns and
// reads `args/agent/log/phase/pipeline/parallel` as globals the runtime injects.
// So it is loaded as source and wrapped in an AsyncFunction with exactly those
// parameters -- the closest stand-in for how the real engine runs it.
//
// Usage: node swe_loop_stub.mjs <script.json>
//   script.json = { "args": {...}, "responses": { "<agent label>": <result> } }
//   A response may be an array, consumed one per call with the last repeating.
//   JSON null means "the agent returned nothing".
// Prints {journal, logs, phases, result, error} as JSON on stdout.

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const script = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const here = dirname(fileURLToPath(import.meta.url))
const loopPath = resolve(here, '../../plugins/swe/workflows/swe-loop.js')
const source = readFileSync(loopPath, 'utf8').replace(/^export const meta/m, 'const meta')

const journal = []
const logs = []
const phases = []
const responses = script.responses || {}
const cursors = new Map()

// Enough of a happy path that a test scripts only the calls it is about.
const defaultResult = label => {
  const [kind, identifier] = label.split(':')
  if (kind === 'frontier') return { issues: [] }
  if (kind === 'implement') {
    return { status: 'DONE', branch: `knack/slice/${identifier}`, summary: `${identifier} implemented` }
  }
  if (kind === 'review' || kind === 're-review') return { verdict: 'pass' }
  if (kind === 'spec-review') return { findings: [] }
  if (kind === 'merge') return { merged: true, detail: 'merged' }
  if (kind === 'ship') return { prUrl: 'https://example.test/pr/1' }
  return 'ok'
}

const scriptedResult = label => {
  if (!Object.prototype.hasOwnProperty.call(responses, label)) return defaultResult(label)
  const scripted = responses[label]
  if (!Array.isArray(scripted)) return scripted
  const call = cursors.get(label) || 0
  cursors.set(label, call + 1)
  return scripted[Math.min(call, scripted.length - 1)]
}

const agent = async (prompt, options = {}) => {
  const label = options.label || '(unlabeled)'
  journal.push({ label, phase: options.phase || null, agentType: options.agentType || null, prompt })
  return scriptedResult(label)
}

const log = line => logs.push(String(line))
const phase = title => phases.push(String(title))

const pipeline = async (items, ...stages) => {
  const outcomes = []
  for (const item of items) {
    let carried
    for (const stage of stages) carried = await stage(carried, item)
    outcomes.push(carried)
  }
  return outcomes
}

const parallel = async factories => Promise.all(factories.map(factory => factory()))

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const run = new AsyncFunction('args', 'agent', 'log', 'phase', 'pipeline', 'parallel', source)

let result = null
let error = null
try {
  result = await run(script.args, agent, log, phase, pipeline, parallel)
} catch (thrown) {
  error = thrown.message
}
process.stdout.write(JSON.stringify({ journal, logs, phases, result, error }, null, 2))
