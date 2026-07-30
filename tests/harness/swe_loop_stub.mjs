// Drives plugins/swe/workflows/swe-loop.js against scripted agent results.
//
// The workflow is written for a runtime that wraps the file in an async
// function (it ends in a top-level `return`), so it is compiled here the same
// way rather than imported as a module.
//
// Usage: node swe_loop_stub.mjs <scenario.json>
//   scenario = { args, responses: [{ match: <regex on the agent label>, result }] }
// Prints { calls: [{label, prompt, options}], result } as JSON on stdout.
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const scenario = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const source = readFileSync(resolve(here, '../../plugins/swe/workflows/swe-loop.js'), 'utf8')

const calls = []
const agent = async (prompt, options = {}) => {
  const label = options.label || ''
  calls.push({ label, prompt, options })
  const rule = scenario.responses.find(entry => new RegExp(entry.match).test(label))
  return rule ? rule.result : null
}
const log = () => {}
const phase = () => {}
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
const body = source.replace(/^export const meta/m, 'const meta')
const run = new AsyncFunction('agent', 'log', 'phase', 'pipeline', 'parallel', 'args', body)
const result = await run(agent, log, phase, pipeline, parallel, scenario.args)

process.stdout.write(JSON.stringify({ calls, result }))
