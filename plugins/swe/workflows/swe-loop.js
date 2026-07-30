export const meta = {
  name: 'swe-loop',
  description:
    'Conductor for the swe spine after spec approval: slice the spec into tracker issues, run the frontier loop (implement, then merge each round) until it drains, review the assembled work against the spec once with bounded fixes, then ship a draft PR',
  whenToUse:
    'Launched by /start-loop once a spec carries the approval marker. Requires args {specPath, slug, containerId, baseBranch, scriptsDir, issueId?} — containerId is the tracker container holding the slices, baseBranch is the integration branch every slice merges into, scriptsDir is the absolute path to the installed swe plugin\'s scripts/ dir. Pass issueId only to resume against one already-published slice set. Optional frontierCmd is a command string that prints the container\'s workable-issue JSON array on stdout; pass it when the resolved tracker has a deterministic frontier query, omit it to keep the reference-driven agent query. Optional roles maps any of planner|implementer|reviewer|publisher to "codex" to run that role through swe:codex-delegator on the local Codex CLI (unlisted roles stay on Claude). Returns {prUrl, slicesCompleted, escalations}; it never prompts the user mid-run.',
  phases: [
    { title: 'Slice', detail: 'publish the spec as vertical slices on the tracker' },
    { title: 'Implement', detail: 'frontier rounds: implement in parallel, then one agent merges and marks the round' },
    { title: 'Review', detail: 'one adherence review of the assembled work, bounded fixes, one re-entry' },
    { title: 'Ship', detail: 'ship-pr: atomic commits, push, draft PR' },
  ],
}

// How many fix rounds the assembled review gets before its surviving findings
// are escalated, and how many times those findings may re-enter the frontier
// loop as fresh slices. Both are the run's cost ceiling -- widening them
// silently is the bug the colocated static test guards against.
const MAX_FIX_ROUNDS = 2
const SPEC_REVIEW_REENTRIES = 1
// The frontier is tracker-derived, so a node that never settles would spin
// forever; this cap turns that into a loud escalation instead.
const MAX_FRONTIER_ROUNDS = 25
const SLICE_COMPLETE_MARKER = '<!-- knack:slice-complete -->'
// The frontier agent call is the one place where a harness/API failure (an
// overloaded-API 529 killed two observed runs after zero work) takes the whole
// run down, so a null result -- the shape every such failure arrives in -- is
// retried with backoff. A non-null result carrying `error` is a real,
// deterministic tracker failure and is never retried.
const FRONTIER_ATTEMPTS = 3
const FRONTIER_BACKOFF_MS = [30000, 120000]
// Tight on purpose: the hint names a missing or rejected credential, and every
// string a tracker query emits for that names a 401/403, "credential",
// "api key", "login", or "unauthorized"/"forbidden". A bare `token` is absent
// because it false-positives on token-limit errors -- a wrong hint sent one
// run's operator debugging a valid credential.
const AUTH_ERROR_SIGNATURE = /\b40[13]\b|unauthorized|forbidden|credential|api[ _-]?key|login/i
const AUTH_HINT =
  ' — this looks like an auth failure: the tracker credential named in the tracker reference is missing or invalid in the agent environment; fix it and resume'

// `args` may arrive as the caller's raw JSON string rather than the parsed
// object, depending on the invoking runtime; normalize so both work. A string
// that is not JSON is a different failure from a well-formed tuple missing
// fields, so it gets its own message.
let argsParseError = null
const ARGS =
  typeof args === 'string'
    ? (() => {
        try {
          return JSON.parse(args)
        } catch (e) {
          argsParseError = e.message
          return null
        }
      })()
    : args
if (argsParseError) {
  throw new Error(
    `swe-loop received args as a string that is not JSON (${argsParseError}). Pass the handoff tuple {specPath, slug, containerId, baseBranch, scriptsDir, issueId?} as an object or as its JSON encoding.`,
  )
}

const REQUIRED_ARGS = ['specPath', 'slug', 'containerId', 'baseBranch', 'scriptsDir']
const missing = REQUIRED_ARGS.filter(key => !ARGS || !ARGS[key])
if (missing.length) {
  throw new Error(
    `swe-loop requires args {specPath, slug, containerId, baseBranch, scriptsDir, issueId?} — missing: ${missing.join(', ')}. /start-loop passes the handoff tuple plus the run's integration branch and the installed plugin's scripts directory.`,
  )
}
const specPath = ARGS.specPath
const slug = ARGS.slug
const containerId = ARGS.containerId
const baseBranch = ARGS.baseBranch
// Absolute path to the installed plugin's scripts/ dir: the target repo does
// not contain frontier.py — only the plugin installation does.
const scriptsDir = ARGS.scriptsDir
if (!scriptsDir.startsWith('/')) {
  throw new Error(
    `swe-loop got a relative scriptsDir (${scriptsDir}). It must be the EXPANDED absolute path to the installed swe plugin's scripts/ dir — a value like "\${CLAUDE_PLUGIN_ROOT}/scripts" means the variable was passed through unexpanded, and the subagents' shells do not define it.`,
  )
}
const resumeIssueId = ARGS.issueId || null
// Optional, opaque: a command that prints the container's workable-issue array
// on stdout and exits non-zero on failure. The launcher resolves the tracker
// anyway, so it is the layer that knows whether the tracker's reference names a
// deterministic frontier query; this file only embeds the string as data.
// Absent, the reference-driven agent query below runs unchanged.
const frontierCmd = ARGS.frontierCmd || null
if (frontierCmd !== null && typeof frontierCmd !== 'string') {
  throw new Error(
    `swe-loop got a non-string frontierCmd (${JSON.stringify(ARGS.frontierCmd)}). It must be a single command string that prints the workable-frontier JSON array on stdout and exits non-zero on failure.`,
  )
}

// Tracker mechanics never live in this file: prompts resolve the repo's
// tracker at runtime and follow the matching to-issues reference (installed
// beside scripts/ in the same plugin), so the loop runs the same over
// whichever tracker the repo pins.
const trackerRefsDir = `${scriptsDir.replace(/\/scripts\/?$/, '')}/skills/to-issues/references`
const trackerGuide = `Tracker: resolve this repo's tracker per the to-issues skill — an "Issue tracker:" line in the repo's AGENTS.md/CLAUDE.md wins, else the skill's selection ladder — then follow the matching reference in ${trackerRefsDir}/ for every tracker operation.`

// ---- role routing -------------------------------------------------------
// The launcher may route any capability role to Codex; every other agent
// (frontier, merge, tracker bookkeeping) is loop plumbing and stays on the
// default workflow subagent.
const ROUTABLE_ROLES = ['planner', 'implementer', 'reviewer', 'publisher']
const ROLE_PROVIDERS = ['claude', 'codex']
const roleRouting = ARGS.roles || {}
// Object.entries silently yields [] for a boolean or number, which would read
// as "no routing requested" and discard the caller's intent without a word.
if (typeof roleRouting !== 'object' || Array.isArray(roleRouting)) {
  throw new Error(
    `swe-loop got a non-object roles value (${JSON.stringify(ARGS.roles)}). Pass a map like {"reviewer": "codex"} with keys among ${ROUTABLE_ROLES.join(', ')}.`,
  )
}
const invalidRoles = Object.entries(roleRouting).filter(
  ([role, provider]) => !ROUTABLE_ROLES.includes(role) || !ROLE_PROVIDERS.includes(provider),
)
if (invalidRoles.length) {
  throw new Error(
    `swe-loop got an invalid roles map (${JSON.stringify(roleRouting)}). Keys must be among ${ROUTABLE_ROLES.join(', ')}; values must be "claude" or "codex".`,
  )
}
const agentTypeFor = role => (roleRouting[role] === 'codex' ? 'swe:codex-delegator' : `swe:${role}`)

// ---- agent contracts --------------------------------------------------------
const FRONTIER_SCHEMA = {
  type: 'object',
  required: ['issues'],
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'identifier', 'title'],
        properties: { id: { type: 'string' }, identifier: { type: 'string' }, title: { type: 'string' } },
      },
    },
    error: {
      type: 'string',
      description: 'set ONLY when the frontier could not be determined (auth, network, failed tracker query). An empty issues list means the frontier is genuinely drained, never that a query failed.',
    },
  },
}

const IMPLEMENTER_SCHEMA = {
  type: 'object',
  required: ['status', 'branch', 'summary'],
  properties: {
    status: { type: 'string', enum: ['DONE', 'DONE_WITH_CONCERNS', 'NEEDS_CONTEXT', 'BLOCKED'] },
    branch: { type: 'string', description: 'the branch you committed the slice to' },
    summary: { type: 'string', description: 'one paragraph: what landed and how it was verified' },
  },
}

// One review, one schema. The loop reviews the assembled branch once rather
// than reviewing each slice and then re-reviewing the same lines through
// several lenses: in the run that motivated this, 52% of the token spend went
// on reading the same diff three times.
const REVIEW_SCHEMA = {
  type: 'object',
  required: ['verdict'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'findings', 'did-not-complete'] },
    findings: {
      type: 'array',
      description: 'REQUIRED and non-empty when verdict is "findings"; omit it for any other verdict',
      items: { type: 'string', description: 'one required change, opening with a file:line anchor and then what to do' },
    },
    detail: {
      type: 'string',
      description: 'REQUIRED when verdict is "did-not-complete": what stopped the review (timeout, tool failure, exit code). Never a judgment about the code.',
    },
  },
}

// One agent settles a whole round: merges are sequential anyway (two agents
// merging into the same branch race on the index), and spawning a merge agent
// plus a comment agent per slice cost 7M cache reads in the motivating run to
// do deterministic git and one API call each.
const SETTLE_SCHEMA = {
  type: 'object',
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        required: ['identifier', 'merged', 'marked', 'detail'],
        properties: {
          identifier: { type: 'string' },
          merged: { type: 'boolean' },
          marked: { type: 'boolean', description: 'whether the slice-complete marker was posted; a merged slice whose marker did not post will be re-implemented by a resumed run' },
          detail: { type: 'string' },
        },
      },
    },
  },
}

const SHIP_SCHEMA = {
  type: 'object',
  required: ['prUrl'],
  properties: { prUrl: { type: 'string' } },
}

// ---- prompts ----------------------------------------------------------------
const tupleFor = issueId => JSON.stringify({ specPath, slug, containerId, issueId })
// Display-only shortening: log lines and escalation reasons. Never applied to
// findings handed to an agent that has to act on them.
const clip = text => String(text == null ? '' : text).replace(/\s+/g, ' ').trim().slice(0, 200)
const branchFor = issue => `knack/slice/${issue.identifier}`
const numbered = items => items.map((item, i) => `${i + 1}. ${typeof item === 'string' ? item : JSON.stringify(item)}`).join('\n')

const promptSlicer = () => `Slice the approved spec at ${specPath} into tracker issues.

Handoff tuple: ${tupleFor(null)}

Run the to-issues skill against this spec and publish every slice into tracker
container ${containerId}, wiring blocked-by edges as native tracker relations.
The skill dedupes against the container's spec marker: on a resumed run reuse
what is already published rather than creating a second set of slices.

Before publishing each slice, pipe its drafted body through
   uv run ${scriptsDir}/validate_artifacts.py issue -
and fix whatever it rejects; publish only bodies that pass.`

// Step 1 is the only part of the frontier prompt frontierCmd changes; steps 2-4
// follow the tracker reference either way. With no frontierCmd this string is
// what the prompt has always carried, byte for byte.
const frontierStep1 = frontierCmd
  ? `1. Run EXACTLY this command with Bash and construct no other query — no
   improvised tracker calls, no edits to the command, no substitutions:

       ${frontierCmd}

   Its stdout is the container's workable-issue array; take each entry as
   {id, identifier, title}. On a NON-ZERO exit put stderr verbatim in the
   "error" field and return an empty issues list -- an empty list with no
   error means the run is finished, so never report a failure that way.`
  : `1. Compute the workable frontier of container ${containerId} per the
   reference's "swe-loop frontier" section — open issues with no open blocker
   and no ready-for-human label, each as {id, identifier, title}. Scripts the
   reference names live in ${scriptsDir}. If the query FAILS (auth, network,
   missing credential, non-zero script exit), put the failure text in the
   "error" field and return an empty issues list -- an empty list with no
   error means the run is finished, so never report a failure that way.`

const promptFrontier = () => `Report this run's workable slices as JSON.

${trackerGuide}

${frontierStep1}
2. For each returned issue read its tracker comments per the reference.
3. DROP every issue whose comments contain the literal marker
   ${SLICE_COMPLETE_MARKER} — that slice is already implemented on a branch in
   this run even though its tracker state has not advanced yet.
4. Return the surviving issues.`

const promptImplementer = issue => `Execute this bounded task: implement one slice of ${specPath}, end to end.

Handoff tuple: ${tupleFor(issue.id)}
Slice: ${issue.identifier} — ${issue.title}

1. Create or check out branch ${branchFor(issue)} from ${baseBranch} and work
   only there — on a resumed or retried slice the branch may already exist,
   with earlier commits on it.
2. Implement the slice per the implement skill's per-slice discipline: prove
   the behavior first (tdd), then lint, types, tests.
3. COMMIT the work to ${branchFor(issue)}. Do not push, do not merge, do not
   open a PR — the conductor merges and ships.
4. Comment progress on tracker issue ${issue.identifier}.
5. Report {status, branch, summary}; "branch" is the branch you actually
   committed to. NEEDS_CONTEXT or BLOCKED means you could not finish: name
   exactly what is missing instead of guessing.`

const promptReview = () => `Review the assembled implementation against its spec, through one lens:
does the code do what the spec asked, correctly?

Under review: the work this run merged into ${baseBranch}. Establish the diff
yourself — the slice merges are on ${baseBranch} and each carries a
knack/slice/<identifier> branch — and say in your first finding if you could
not establish it rather than reviewing a guess.
Spec: ${specPath}

This is the run's ONLY code review, so judge adherence end to end: behavior the
spec asked for and the code lacks, behavior that diverges from what the spec
asked, and missing tests for either. Slice branches were already gated on their
own lint/types/tests passing — do not re-litigate style or restate what the
tests already prove.

Verdict "pass" when nothing must change; otherwise "findings" with at least one
entry, one per required change, each opening with a file:line anchor and then
the fix. "findings" with an empty list is not a valid answer.

An unresolved finding is quoted verbatim into the tracker comment a later
session resumes from, so it must stand alone: the anchor is what makes it
actionable without this run's context.

Verdict "did-not-complete" means YOU could not finish the review — a delegated
run timed out, a tool failed, a command exited non-zero — and is never a
judgment about the code. Put what stopped you in "detail" and return no
findings. An infrastructure failure must never appear as a finding: a fixer
would act on it.`

const promptFixer = (findings, round) => `Execute this bounded task: apply review findings to ${baseBranch}.

Findings to resolve (fix round ${round}/${MAX_FIX_ROUNDS}):
${numbered(findings)}

Work directly on ${baseBranch} in the main worktree at the repo root — the
slices are already merged there. Apply every finding, re-run lint/types/tests,
and commit. Do not push and do not merge. Return a concise completion note;
this call has no additional output schema.`

const promptEscalationNote = (issue, reason) => `Post one comment on tracker issue ${issue.identifier}.

${trackerGuide}

The comment body is exactly:

**swe-loop escalation** — ${clip(reason)}

Post nothing else and change no issue fields.`

const promptSettle = slices => `Settle this round's finished slices into ${baseBranch}, in the main worktree at
the repo root. Work through them IN THE ORDER GIVEN, one at a time.

${trackerGuide}

Slices:
${numbered(slices.map(slice => `${slice.issue.identifier} on ${slice.branch} — ${clip(slice.summary)}`))}

For each slice, in order:
1. git checkout ${baseBranch} && git merge --no-ff <its branch>
2. On conflict, resolve it per the merge-conflicts skill and complete the merge.
   If you cannot resolve it confidently, git merge --abort, record
   merged:false with the reason, and move on to the next slice — never force a
   resolution you are unsure of and never abandon the remaining slices.
3. Only after its merge succeeds, post one comment on that slice's tracker
   issue whose body is exactly the marker line then its one-line summary:

   ${SLICE_COMPLETE_MARKER}
   <the summary given above>

   Post the marker verbatim — it is what makes a resumed run skip the slice.
   Record marked:true only if the comment actually posted.

Return one {identifier, merged, marked, detail} per slice, in the same order.
Do not push. Marking only after a confirmed merge is deliberate: a resumed run
re-implementing a merged slice is recoverable, losing one is not.`

const promptFileFindings = findings => `File surviving review findings as fix slices in tracker container ${containerId}.

Spec: ${specPath}
Findings:
${numbered(findings)}

One issue per finding that needs code. Write bodies against the to-issues
issue template and check each with
   uv run ${scriptsDir}/validate_artifacts.py issue -
(body on stdin) before publishing. Do not re-file a finding that already has
an open issue in the container.`

const promptShip = () => `Ship the finished work on ${baseBranch}.

Handoff tuple: ${tupleFor(null)}

Run the ship-pr skill: verify lint/types/tests, group any uncommitted work into
atomic commits, push ${baseBranch}, and open a DRAFT pull request. Tracker
links, issue ids, and tracker-only content never appear in commit messages, the
PR title, or the PR body. Return the PR URL.`

const promptRunSummary = summary => `Post this run's summary as one comment on tracker container ${containerId},
per the tracker reference's container-comment convention.

${trackerGuide}

Run: ${slug} — spec ${specPath}, integration branch ${baseBranch}.

The comment body is a short "swe-loop run summary" heading followed by this
payload verbatim in a fenced json block:

${JSON.stringify(summary, null, 2)}

Post nothing else and change no container fields.`

// ---- run state --------------------------------------------------------------
const slicesCompleted = []
const escalations = []
// Issues settled (merged or escalated) earlier in THIS run. The tracker cannot
// tell us about them yet -- their state only advances when the PR lands.
const settled = new Set()

const escalateRun = (title, reason, details = []) => {
  escalations.push({ issue: null, title, reason, findings: details })
  log(`ESCALATED ${title}: ${reason}`)
}

// A slice escalates only when it could not be implemented or merged, so this
// carries no findings: code findings are run-level now, raised by the assembled
// review against the integration branch and kept verbatim in the run summary.
const escalate = async (issue, reason) => {
  settled.add(issue.id)
  escalations.push({ issue: issue.identifier, title: issue.title, reason, findings: [] })
  log(`ESCALATED ${issue.identifier}: ${reason}`)
  // Best-effort: an escalation only the run summary knows about is invisible to
  // whoever opens the issue later.
  const noted = await agent(promptEscalationNote(issue, reason), {
    label: `escalation-note:${issue.identifier}`,
    phase: 'Implement',
    effort: 'low',
  })
  if (!noted) log(`${issue.identifier}: escalation comment did not post; the run summary still carries it.`)
  return { issue, state: 'escalated' }
}

// A "findings" verdict carrying no findings is a contract violation, not a
// pass; returning null makes the caller fail the round instead of merging.
const findingsFrom = review => {
  if (review.verdict !== 'findings') return []
  const findings = review.findings || []
  return findings.length ? findings : null
}

// The one path both review sites (initial review, fix-loop re-review) take.
// A review that never finished says nothing about the code: it must not reach
// a fixer as findings and must not spend a fix round. One retry -- a fresh
// delegation, so the delegator's one-invocation-per-delegation contract is
// untouched -- absorbs a flaky run; a second non-completion means the task, not
// the weather, so the run escalates with nothing recorded against the code.
// Returns {findings} or {failed: reason}.
const runReview = async (label, stage) => {
  const request = attemptLabel =>
    agent(promptReview(), {
      label: attemptLabel,
      phase: 'Review',
      agentType: agentTypeFor('reviewer'),
      schema: REVIEW_SCHEMA,
    })
  let review = await request(label)
  if (!review) return { failed: `${stage} returned no verdict` }
  if (review.verdict === 'did-not-complete') {
    log(`${stage} did not complete (${clip(review.detail)}) — retrying once; no fix round consumed.`)
    review = await request(`${label}:retry`)
    if (!review || review.verdict === 'did-not-complete') {
      const detail = review ? clip(review.detail) : 'the retry returned no verdict'
      return {
        failed: `${stage} never completed after one retry (${detail}); ${baseBranch} is unreviewed, no findings recorded, no fix round consumed`,
      }
    }
  }
  const findings = findingsFrom(review)
  if (!findings) return { failed: `${stage} returned verdict "findings" with no findings — contract violation, not a pass` }
  return { findings }
}

const finish = async prUrl => {
  const summary = { prUrl, slicesCompleted, escalations }
  const posted = await agent(promptRunSummary(summary), {
    label: `run-summary:${slug}`,
    phase: 'Ship',
    effort: 'low',
  })
  if (!posted) log('Run-summary comment did not post — the returned summary is the only record of this run.')
  return summary
}

// ---- Slice ------------------------------------------------------------------
phase('Slice')
if (resumeIssueId) {
  log(`Targeted resume on ${resumeIssueId}: slices are already published, skipping the slice phase.`)
} else {
  log(`Slicing ${specPath} into container ${containerId}.`)
  const sliced = await agent(promptSlicer(), { label: `slice:${slug}`, phase: 'Slice', agentType: agentTypeFor('planner') })
  log(sliced ? 'Slicing done.' : 'Slicer returned nothing — the frontier query decides what work actually exists.')
}

// ---- Implement --------------------------------------------------------------
// Null means the agent call itself died (harness or API), which is transient;
// retry it with backoff. Anything non-null -- including a result carrying
// `error` -- is the tracker's own answer and is returned to the caller as-is.
const requestFrontier = async label => {
  for (let attempt = 1; attempt <= FRONTIER_ATTEMPTS; attempt += 1) {
    const frontier = await agent(promptFrontier(), {
      label: attempt === 1 ? label : `${label}:retry${attempt - 1}`,
      phase: 'Implement',
      effort: 'low',
      schema: FRONTIER_SCHEMA,
    })
    if (frontier) return frontier
    if (attempt === FRONTIER_ATTEMPTS) return null
    const wait = FRONTIER_BACKOFF_MS[attempt - 1]
    log(`Frontier attempt ${attempt}/${FRONTIER_ATTEMPTS} returned nothing — retrying in ${wait / 1000}s.`)
    await new Promise(resolve => setTimeout(resolve, wait))
  }
  return null
}

const runFrontierLoop = async passLabel => {
  phase('Implement')
  for (let round = 1; round <= MAX_FRONTIER_ROUNDS; round += 1) {
    const frontier = await requestFrontier(`frontier:${passLabel}:${round}`)
    if (!frontier || frontier.error) {
      // Verbatim and unclipped: this reason is the only record of what actually
      // failed, and a truncated 529 or GraphQL error reads as a mystery.
      const reason = frontier
        ? String(frontier.error)
        : `frontier agent returned nothing after ${FRONTIER_ATTEMPTS} attempts`
      escalateRun('frontier query', AUTH_ERROR_SIGNATURE.test(reason) ? `${reason}${AUTH_HINT}` : reason)
      log(`Frontier query failed (${reason}) — stopping the ${passLabel} loop rather than reading it as an empty frontier.`)
      return
    }
    const pending = (frontier.issues || []).filter(issue => !settled.has(issue.id))
    if (!pending.length) {
      log(`Frontier drained on round ${round} of the ${passLabel} loop.`)
      return
    }
    log(`Round ${round} (${passLabel}): ${pending.length} slice(s) — ${pending.map(issue => issue.identifier).join(', ')}`)

    // Implement only. A slice's gate is its own lint/types/tests, which the
    // implementer runs and which cost no tokens; the code is reviewed once,
    // assembled, after the loop drains.
    const outcomes = await parallel(
      pending.map(issue => async () => {
        const result = await agent(promptImplementer(issue), {
          label: `implement:${issue.identifier}`,
          phase: 'Implement',
          agentType: agentTypeFor('implementer'),
          isolation: 'worktree',
          schema: IMPLEMENTER_SCHEMA,
        })
        if (!result) return escalate(issue, 'implementer returned no result (skipped or errored)')
        if (result.status === 'NEEDS_CONTEXT' || result.status === 'BLOCKED') {
          return escalate(issue, `implementer reported ${result.status}: ${clip(result.summary)}`)
        }
        const branch = result.branch || branchFor(issue)
        log(`${issue.identifier}: implemented (${result.status}) on ${branch}.`)
        return { issue, state: 'implemented', summary: result.summary, branch }
      }),
    )

    // One agent merges the whole round in order and marks each slice as it
    // lands: merges must be sequential anyway (two agents merging into the
    // same working copy race on the index), so per-slice merge and marker
    // agents bought nothing but their own context.
    const ready = outcomes.filter(Boolean).filter(outcome => outcome.state === 'implemented')
    let merged = 0
    if (ready.length) {
      const settlement = await agent(promptSettle(ready), {
        label: `settle:${passLabel}:${round}`,
        phase: 'Implement',
        schema: SETTLE_SCHEMA,
      })
      const results = settlement ? settlement.results || [] : []
      for (const outcome of ready) {
        const issue = outcome.issue
        const result = results.find(entry => entry.identifier === issue.identifier)
        if (!result || !result.merged) {
          await escalate(issue, `merge into ${baseBranch} failed: ${result ? clip(result.detail) : 'the settle agent reported nothing for this slice'}`)
          continue
        }
        settled.add(issue.id)
        slicesCompleted.push(issue.identifier)
        merged += 1
        log(`${issue.identifier}: merged ${outcome.branch} into ${baseBranch}.`)
        // Deliberate trade-off: marking only after a confirmed merge accepts a
        // crash-after-merge window (a resumed run re-implements a slice already
        // in the base branch) rather than losing a slice whose merge failed
        // after it was already marked complete.
        if (!result.marked) {
          escalateRun(`slice-complete marker: ${issue.identifier}`, `the marker did not post after merging into ${baseBranch}; a resumed run may re-implement this slice`)
        }
      }
    }
    // Anything the pipeline dropped (null outcome, unknown state) would come
    // back on the next frontier query and be re-spawned forever; settle it.
    for (const issue of pending) {
      if (settled.has(issue.id)) continue
      await escalate(issue, 'the implement pipeline produced no settled outcome for this slice')
    }
    log(`Round ${round} (${passLabel}) summary: ${merged} merged, ${pending.length - merged} escalated, ${escalations.length} escalation(s) so far.`)
  }
  log(`Frontier loop hit its ${MAX_FRONTIER_ROUNDS}-round cap without draining — stopping and escalating.`)
  escalateRun('frontier loop', `hit the ${MAX_FRONTIER_ROUNDS}-round cap; slices remain unworked`)
}

await runFrontierLoop('implement')

// Reviewing and shipping an unimplemented base branch burns high-tier agents on
// nothing and can open a PR over an empty diff; stop at the summary instead.
if (!slicesCompleted.length && escalations.length) {
  log(`No slice merged into ${baseBranch} and ${escalations.length} escalation(s) stand — skipping review and ship.`)
  return await finish(null)
}

// ---- Review -----------------------------------------------------------------
// One review of the assembled work, then bounded fixes against it. Findings
// are fixed in place on the integration branch: re-slicing them onto the
// tracker and re-entering the frontier loop costs a planner, a frontier query,
// an implementer and a settle agent per pass, so it is the last resort below,
// not the first response.
phase('Review')
// `pass` distinguishes the re-entry's labels from the first pass's: without it
// both passes emit `fix:1`, and a transcript cannot say which round it is.
const settleFindings = async (pass = '') => {
  let reviewed = await runReview(`review${pass}:assembled`, 'assembled review')
  if (reviewed.failed) {
    escalateRun('assembled review', reviewed.failed)
    return []
  }
  let findings = reviewed.findings
  for (let fixRound = 1; findings.length && fixRound <= MAX_FIX_ROUNDS; fixRound += 1) {
    log(`Fix round ${fixRound}/${MAX_FIX_ROUNDS} for ${findings.length} finding(s).`)
    const fixed = await agent(promptFixer(findings, fixRound), {
      label: `fix${pass}:${fixRound}`,
      phase: 'Review',
      agentType: agentTypeFor('implementer'),
    })
    if (!fixed) {
      escalateRun(`fix round ${fixRound}`, `the fixer returned no result; ${findings.length} finding(s) stand`)
      return findings
    }
    reviewed = await runReview(`re-review${pass}:${fixRound}`, `re-review after fix round ${fixRound}`)
    if (reviewed.failed) {
      escalateRun('assembled review', reviewed.failed)
      return findings
    }
    findings = reviewed.findings
  }
  return findings
}

let openFindings = await settleFindings()
let reentries = 0
while (openFindings.length && reentries < SPEC_REVIEW_REENTRIES) {
  reentries += 1
  log(`${openFindings.length} finding(s) survived ${MAX_FIX_ROUNDS} fix rounds — filing them as slices (re-entry ${reentries}/${SPEC_REVIEW_REENTRIES}).`)
  const filed = await agent(promptFileFindings(openFindings), {
    label: `file-findings:${reentries}`,
    phase: 'Review',
    agentType: agentTypeFor('planner'),
  })
  if (!filed) {
    log('Could not file the findings as fix slices — collecting them as escalations instead.')
    break
  }
  await runFrontierLoop(`review-${reentries}`)
  phase('Review')
  openFindings = await settleFindings(`-r${reentries}`)
}
if (openFindings.length) {
  escalateRun(
    `${openFindings.length} finding(s) survived review`,
    `${openFindings.length} finding(s) survived ${MAX_FIX_ROUNDS} fix rounds on ${baseBranch}`,
    openFindings,
  )
}
log(`Review settled: ${openFindings.length} open finding(s), ${escalations.length} escalation(s) total.`)

// ---- Ship -------------------------------------------------------------------
phase('Ship')
const shipped = await agent(promptShip(), {
  label: `ship:${slug}`,
  phase: 'Ship',
  agentType: agentTypeFor('publisher'),
  schema: SHIP_SCHEMA,
})
if (!shipped) {
  escalateRun('ship-pr', `publisher returned no PR URL; ${baseBranch} is merged but unpublished`)
  log(`Ship failed — ${baseBranch} holds the merged work but no PR was opened.`)
} else {
  log(`Draft PR: ${shipped.prUrl}`)
}

return await finish(shipped ? shipped.prUrl : null)
