// Drives plugins/swe/workflows/swe-loop.js end to end with scripted agent
// results, so conductor behavior (retries, escalations, what a prompt says) is
// testable without spawning a single real agent.
//
// The workflow is written for a runtime that supplies `args/agent/log/phase/
// pipeline/parallel` as ambient bindings and permits a top-level `return`, so
// it is compiled here as the body of an async function with those parameters
// rather than imported as a module. `setTimeout` is a parameter too: the stub's
// version records the requested delay and fires immediately, which is what
// makes a 30 s/120 s backoff assertable in a millisecond test.
//
// Usage: node swe_loop_stub.mjs <config.json>, JSON result on stdout.
// Config: {
//   workflowPath, args,
//   responses: [{ match: <regex on the call label>, result: <any|null>, times? }],
//   defaultResult: <any|null>   // for labels no response matches
// }
import { readFileSync } from 'node:fs'

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const source = readFileSync(config.workflowPath, 'utf8').replace(/^export const meta =/m, 'const meta =')

const calls = []
const logs = []
const phases = []
const sleeps = []
const scripted = (config.responses || []).map(response => ({
  pattern: new RegExp(response.match),
  result: response.result === undefined ? {} : response.result,
  remaining: response.times === undefined ? Infinity : response.times,
}))
const defaultResult = config.defaultResult === undefined ? {} : config.defaultResult

const agent = async (prompt, options = {}) => {
  const label = options.label || ''
  calls.push({ label, phase: options.phase || null, agentType: options.agentType || null, prompt })
  const hit = scripted.find(response => response.remaining > 0 && response.pattern.test(label))
  if (!hit) return defaultResult
  hit.remaining -= 1
  return hit.result
}
const log = line => logs.push(String(line))
const phase = title => phases.push(String(title))
const pipeline = async (items, ...stages) =>
  Promise.all(
    items.map(async item => {
      let carried = null
      for (const stage of stages) carried = await stage(carried, item)
      return carried
    }),
  )
const parallel = async fns => Promise.all(fns.map(fn => fn()))
const stubSetTimeout = (fn, ms) => {
  sleeps.push(ms)
  return setTimeout(fn, 0)
}

const run = new AsyncFunction('args', 'agent', 'log', 'phase', 'pipeline', 'parallel', 'setTimeout', source)

let summary = null
let error = null
try {
  summary = await run(config.args, agent, log, phase, pipeline, parallel, stubSetTimeout)
} catch (e) {
  error = e.message
}

process.stdout.write(JSON.stringify({ summary, error, calls, logs, phases, sleeps }, null, 2))
