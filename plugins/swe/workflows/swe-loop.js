export const meta = {
  name: 'swe-loop',
  description:
    'Conductor for the swe spine after spec approval: slice the spec into tracker issues, run the frontier loop (implement -> review -> bounded fix -> merge) until it drains, review the assembled work against the spec through three lenses, then ship a draft PR',
  whenToUse:
    'Launched by /start-loop once a spec carries the approval marker. Requires args {specPath, slug, containerId, baseBranch, scriptsDir, issueId?} — containerId is the tracker container holding the slices, baseBranch is the integration branch every slice merges into, scriptsDir is the absolute path to the installed swe plugin\'s scripts/ dir. Pass issueId only to resume against one already-published slice set. Returns {prUrl, slicesCompleted, escalations, cutList}; it never prompts the user mid-run.',
  phases: [
    { title: 'Slice', detail: 'publish the spec as vertical slices on the tracker' },
    { title: 'Implement', detail: 'frontier rounds: implement, review, bounded fixes, sequential merge' },
    { title: 'Spec review', detail: 'three lenses against the spec, one fix re-entry' },
    { title: 'Ship', detail: 'ship-pr: atomic commits, push, draft PR' },
  ],
}

// How many implement/review rounds a single slice gets before it is escalated
// unmerged, and how many times spec-review findings may re-enter the frontier
// loop. Both are the run's cost ceiling -- widening them silently is the bug
// the colocated static test guards against.
const MAX_FIX_ROUNDS = 2
const SPEC_REVIEW_REENTRIES = 1
// The frontier is tracker-derived, so a node that never settles would spin
// forever; this cap turns that into a loud escalation instead.
const MAX_FRONTIER_ROUNDS = 25
const SLICE_COMPLETE_MARKER = '<!-- knack:slice-complete -->'
const REVIEW_LENSES = ['missed', 'wrong', 'bloat']

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
      description: 'set ONLY when the frontier could not be determined (auth, HTTP, GraphQL). An empty issues list means the frontier is genuinely drained, never that a query failed.',
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

const SLICE_REVIEW_SCHEMA = {
  type: 'object',
  required: ['verdict'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'findings'] },
    findings: {
      type: 'array',
      description: 'REQUIRED and non-empty when verdict is "findings"; omit it when the verdict is "pass"',
      items: { type: 'string', description: 'one required change, naming the file and what to do' },
    },
  },
}

const SPEC_REVIEW_SCHEMA = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['lens', 'title', 'detail', 'severity'],
        properties: {
          lens: { type: 'string', enum: REVIEW_LENSES },
          title: { type: 'string' },
          detail: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
  },
}

const MERGE_SCHEMA = {
  type: 'object',
  required: ['merged', 'detail'],
  properties: { merged: { type: 'boolean' }, detail: { type: 'string' } },
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

const promptFrontier = () => `Report this run's workable slices as JSON.

1. From the repo root run:
   uv run ${scriptsDir}/frontier.py --project ${containerId}
   It prints a JSON array of {id, identifier, title, labels}. If it exits
   non-zero, put its stderr in the "error" field and return an empty issues
   list -- an empty list with no error means the run is finished, so never
   report a failure that way.
2. For each returned issue read its Linear comments (GraphQL at
   https://api.linear.app/graphql; LINEAR_API_KEY is in your environment).
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

const promptSliceReview = (issue, branch) => `Review one slice's diff against its issue contract.

Diff under review: git diff ${baseBranch}...${branch}
Issue: ${issue.identifier} — ${issue.title}
Spec: ${specPath}

Judge this slice only: correctness, edge cases, missing tests, and whether the
diff does what the issue asked — no more, no less. Verdict "pass" when nothing
must change; otherwise "findings" with at least one entry, one per required
change, each naming the file and the fix. "findings" with an empty list is not
a valid answer.`

const promptFixer = (issue, branch, findings) => `Execute this bounded task: apply review findings to an existing slice branch.

Branch: ${branch} (already committed, not checked out here)
Issue: ${issue.identifier} — ${issue.title}
Findings to resolve:
${numbered(findings)}

1. git worktree add ../.swe-fix-${issue.identifier} ${branch} — use exactly
   that path; other fixers run concurrently and a shared path would collide.
2. Apply every finding there, re-run lint/types/tests, and commit to ${branch}.
3. git worktree remove ../.swe-fix-${issue.identifier} — leave none behind.
Do not push and do not merge. Return a concise completion note; this call has
no additional output schema.`

const promptCompletionMark = (issue, summary) => `Post one comment on tracker issue ${issue.identifier} (Linear GraphQL at
https://api.linear.app/graphql; LINEAR_API_KEY is in your environment).

The comment body is exactly the marker line, then a one-line summary:

${SLICE_COMPLETE_MARKER}
${clip(summary)}

Post the marker verbatim — it is what makes a resumed run skip this slice.`

const promptEscalationNote = (issue, reason) => `Post one comment on tracker issue ${issue.identifier} (Linear GraphQL at
https://api.linear.app/graphql; LINEAR_API_KEY is in your environment).

The comment body is exactly:

**swe-loop escalation** — ${clip(reason)}

Post nothing else and change no issue fields.`

const promptMerge = (issue, branch) => `Merge one finished slice into ${baseBranch}, in the main worktree at the repo root.

1. git checkout ${baseBranch}
2. git merge --no-ff ${branch}
3. On conflict, resolve it per the merge-conflicts skill and complete the merge.
   If you cannot resolve it confidently, git merge --abort and return
   merged:false with the reason — never force a resolution you are unsure of.

Return {merged, detail}. Do not push.`

const promptSpecReview = lens => `Review the assembled implementation on ${baseBranch} against its spec through
exactly one lens.

Handoff tuple: ${tupleFor(null)}
Spec: ${specPath}
Your lens: ${lens}
  missed = the spec asks for it and the code lacks it
  wrong  = the code diverges from what the spec asked
  bloat  = the code exceeds the spec; name what to cut

Stay on your lens; another reviewer owns each of the others. Cite the spec
section and file:line for every finding. Severity is high, medium, or low and
means impact only — your lens already types the finding, and the conductor
turns every bloat-lens finding into the run's cut-list.`

const promptFileFindings = findings => `File spec-review findings as fix slices in tracker container ${containerId}.

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

const promptRunSummary = summary => `Post this run's summary as one comment on tracker container ${containerId}
(Linear GraphQL at https://api.linear.app/graphql; LINEAR_API_KEY is in your
environment).

Run: ${slug} — spec ${specPath}, integration branch ${baseBranch}.

The comment body is a short "swe-loop run summary" heading followed by this
payload verbatim in a fenced json block:

${JSON.stringify(summary, null, 2)}

Post nothing else and change no container fields.`

// ---- run state --------------------------------------------------------------
const slicesCompleted = []
const escalations = []
const cutList = []
// Issues settled (merged or escalated) earlier in THIS run. The tracker cannot
// tell us about them yet -- their state only advances when the PR lands.
const settled = new Set()

const escalateRun = (title, reason) => {
  escalations.push({ issue: null, title, reason })
  log(`ESCALATED ${title}: ${reason}`)
}

const escalate = async (issue, reason) => {
  settled.add(issue.id)
  escalations.push({ issue: issue.identifier, title: issue.title, reason })
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

const finish = async prUrl => {
  const summary = { prUrl, slicesCompleted, escalations, cutList }
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
  const sliced = await agent(promptSlicer(), { label: `slice:${slug}`, phase: 'Slice', agentType: 'swe:planner' })
  log(sliced ? 'Slicing done.' : 'Slicer returned nothing — the frontier query decides what work actually exists.')
}

// ---- Implement --------------------------------------------------------------
const runFrontierLoop = async passLabel => {
  phase('Implement')
  for (let round = 1; round <= MAX_FRONTIER_ROUNDS; round += 1) {
    const frontier = await agent(promptFrontier(), {
      label: `frontier:${passLabel}:${round}`,
      phase: 'Implement',
      effort: 'low',
      schema: FRONTIER_SCHEMA,
    })
    if (!frontier || frontier.error) {
      const reason = frontier ? frontier.error : 'frontier agent returned nothing'
      escalateRun('frontier query', `${reason} — if this is an auth or GraphQL failure, LINEAR_API_KEY is missing or invalid in the agent environment; export it and resume`)
      log(`Frontier query failed (${reason}) — stopping the ${passLabel} loop rather than reading it as an empty frontier.`)
      return
    }
    const pending = (frontier.issues || []).filter(issue => !settled.has(issue.id))
    if (!pending.length) {
      log(`Frontier drained on round ${round} of the ${passLabel} loop.`)
      return
    }
    log(`Round ${round} (${passLabel}): ${pending.length} slice(s) — ${pending.map(issue => issue.identifier).join(', ')}`)

    const outcomes = await pipeline(
      pending,
      async (_incoming, issue) => {
        const result = await agent(promptImplementer(issue), {
          label: `implement:${issue.identifier}`,
          phase: 'Implement',
          agentType: 'swe:implementer',
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
      },
      async (outcome, issue) => {
        if (outcome.state === 'escalated') return outcome
        const review = await agent(promptSliceReview(issue, outcome.branch), {
          label: `review:${issue.identifier}`,
          phase: 'Implement',
          agentType: 'swe:reviewer',
          schema: SLICE_REVIEW_SCHEMA,
        })
        if (!review) return escalate(issue, 'slice review returned no verdict')
        const findings = findingsFrom(review)
        if (!findings) return escalate(issue, 'slice review returned verdict "findings" with no findings — contract violation, not a pass')
        return { ...outcome, findings }
      },
      async (outcome, issue) => {
        if (outcome.state === 'escalated') return outcome
        let findings = outcome.findings
        for (let fixRound = 1; findings.length && fixRound <= MAX_FIX_ROUNDS; fixRound += 1) {
          log(`${issue.identifier}: fix round ${fixRound}/${MAX_FIX_ROUNDS} for ${findings.length} finding(s).`)
          const fixed = await agent(promptFixer(issue, outcome.branch, findings), {
            label: `fix:${issue.identifier}:${fixRound}`,
            phase: 'Implement',
            agentType: 'swe:implementer',
          })
          if (!fixed) return escalate(issue, `fix round ${fixRound} returned no result`)
          const review = await agent(promptSliceReview(issue, outcome.branch), {
            label: `re-review:${issue.identifier}:${fixRound}`,
            phase: 'Implement',
            agentType: 'swe:reviewer',
            schema: SLICE_REVIEW_SCHEMA,
          })
          if (!review) return escalate(issue, `re-review after fix round ${fixRound} returned no verdict`)
          const reviewed = findingsFrom(review)
          if (!reviewed) {
            return escalate(issue, `re-review after fix round ${fixRound} returned verdict "findings" with no findings — contract violation, not a pass`)
          }
          findings = reviewed
        }
        if (findings.length) {
          return escalate(issue, `${findings.length} finding(s) survived ${MAX_FIX_ROUNDS} fix rounds; branch left unmerged`)
        }
        return { ...outcome, state: 'passed', findings: [] }
      },
    )

    // Merges are sequential on purpose: two agents merging into the same
    // branch in the same working copy would race on the index.
    const passed = outcomes.filter(Boolean).filter(outcome => outcome.state === 'passed')
    let merged = 0
    for (const outcome of passed) {
      const issue = outcome.issue
      const result = await agent(promptMerge(issue, outcome.branch), {
        label: `merge:${issue.identifier}`,
        phase: 'Implement',
        schema: MERGE_SCHEMA,
      })
      if (!result || !result.merged) {
        await escalate(issue, `merge into ${baseBranch} failed: ${result ? clip(result.detail) : 'merge agent returned nothing'}`)
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
      const marked = await agent(promptCompletionMark(issue, outcome.summary), {
        label: `mark:${issue.identifier}`,
        phase: 'Implement',
        effort: 'low',
      })
      if (!marked) {
        escalateRun(`slice-complete marker: ${issue.identifier}`, `the marker did not post after merging into ${baseBranch}; a resumed run may re-implement this slice`)
        continue
      }
      log(`${issue.identifier}: marked slice-complete on the tracker.`)
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
  log(`No slice merged into ${baseBranch} and ${escalations.length} escalation(s) stand — skipping spec review and ship.`)
  return await finish(null)
}

// ---- Spec review ------------------------------------------------------------
const runSpecReview = async () => {
  const results = await parallel(
    REVIEW_LENSES.map(lens => () =>
      agent(promptSpecReview(lens), {
        label: `spec-review:${lens}`,
        phase: 'Spec review',
        agentType: 'swe:reviewer',
        schema: SPEC_REVIEW_SCHEMA,
      }),
    ),
  )
  // A dead reviewer contributes no findings, which is indistinguishable from a
  // clean lens once flattened — name it first.
  REVIEW_LENSES.forEach((lens, index) => {
    if (!results[index]) escalateRun(`spec review: ${lens}`, `the ${lens} lens returned no result; that lens is unreviewed, not clean`)
  })
  const findings = results.filter(Boolean).flatMap(result => result.findings || [])
  log(`Spec review: ${findings.length} finding(s) across the ${REVIEW_LENSES.join('/')} lenses.`)
  return findings
}

phase('Spec review')
let openFindings = await runSpecReview()
let reentries = 0
while (openFindings.length && reentries < SPEC_REVIEW_REENTRIES) {
  reentries += 1
  log(`Filing ${openFindings.length} finding(s) as fix slices (re-entry ${reentries}/${SPEC_REVIEW_REENTRIES}).`)
  const filed = await agent(promptFileFindings(openFindings), {
    label: `file-findings:${reentries}`,
    phase: 'Spec review',
    agentType: 'swe:planner',
  })
  if (!filed) {
    log('Could not file the findings as fix slices — collecting them as escalations instead.')
    break
  }
  await runFrontierLoop(`spec-review-${reentries}`)
  phase('Spec review')
  openFindings = await runSpecReview()
}
for (const finding of openFindings) {
  // The lens, not the severity, says what a finding is: the bloat lens exists
  // to produce the cut-list.
  if (finding.lens === 'bloat') {
    cutList.push(finding)
    continue
  }
  escalateRun(`${finding.lens}: ${finding.title}`, clip(finding.detail))
}
log(`Spec review settled: ${cutList.length} cut-list item(s), ${escalations.length} escalation(s) total.`)

// ---- Ship -------------------------------------------------------------------
phase('Ship')
const shipped = await agent(promptShip(), {
  label: `ship:${slug}`,
  phase: 'Ship',
  agentType: 'swe:publisher',
  schema: SHIP_SCHEMA,
})
if (!shipped) {
  escalateRun('ship-pr', `publisher returned no PR URL; ${baseBranch} is merged but unpublished`)
  log(`Ship failed — ${baseBranch} holds the merged work but no PR was opened.`)
} else {
  log(`Draft PR: ${shipped.prUrl}`)
}

return await finish(shipped ? shipped.prUrl : null)
