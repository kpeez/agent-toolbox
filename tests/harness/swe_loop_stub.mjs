// Drives plugins/swe/workflows/swe-loop.js with stubbed workflow globals so
// tests can assert on the prompts it emits and the branches it takes.
//
// The conductor is workflow-runtime source, not an importable ES module: it
// reads `args`/`agent`/`log`/`phase`/`pipeline`/`parallel` as free names and
// uses top-level `await` and `return`. So it is compiled the way the runtime
// compiles it — as the body of an async function taking those as parameters.
//
// Usage: node swe_loop_stub.mjs <scenario.json>
// Scenario: {workflowPath, args, results: [{label, result}]} where an agent
// call takes the first entry whose `label` prefixes the call's label, and null
// (the runtime's "agent produced nothing") when none matches.
// Prints {calls, logs, phases, returned} as JSON on stdout.
import { readFileSync } from 'node:fs'

const scenario = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const source = readFileSync(scenario.workflowPath, 'utf8').replace('export const meta', 'const meta')

const calls = []
const logs = []
const phases = []

const agent = async (prompt, options = {}) => {
  const label = options.label || ''
  calls.push({ label, prompt, options })
  const scripted = (scenario.results || []).find(entry => label.startsWith(entry.label))
  return scripted ? scripted.result : null
}
const log = line => logs.push(String(line))
const phase = name => phases.push(name)
// Sequential stand-ins: the tests assert on ordering and on what each stage
// received, not on concurrency.
const pipeline = async (items, ...stages) => {
  const outcomes = []
  for (const item of items) {
    let carried = null
    for (const stage of stages) carried = await stage(carried, item)
    outcomes.push(carried)
  }
  return outcomes
}
const parallel = async thunks => {
  const results = []
  for (const thunk of thunks) results.push(await thunk())
  return results
}

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const run = new AsyncFunction('args', 'agent', 'log', 'phase', 'pipeline', 'parallel', source)
const returned = await run(scenario.args, agent, log, phase, pipeline, parallel)

process.stdout.write(JSON.stringify({ calls, logs, phases, returned }, null, 2))
