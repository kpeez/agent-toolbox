export const meta = {
  name: 'swe-loop',
  description:
    'Conductor for the swe workflow after spec approval and splitting: run the implement loop (implement, then merge each round) until it drains, review the assembled work against the spec once with bounded fixes, then ship a draft PR',
  whenToUse:
    'Launched by /start-loop once a spec carries the approval marker and its tasks are published on the tracker — the launcher tasks before launching, so the conductor starts at the workable query. Requires args {specPath, slug, containerId, baseBranch, scriptsDir} — containerId is the tracker container holding the tasks, baseBranch is the integration branch every task merges into, scriptsDir is the absolute path to the installed swe plugin\'s scripts/ dir. Optional workableCmd is a command string that prints the container\'s workable-issue JSON array on stdout; already excluding tasks this run merged; pass it when the resolved tracker has a deterministic workable query, omit it to keep the reference-driven agent query. Optional roles maps any of planner|implementer|reviewer|publisher to a provider ("claude" or "opencode") to run that role on that provider through its forwarder agent. Unlisted roles take the default routing: implementer and reviewer run on OpenCode Go (each pinned to its own model by the plugin\'s MCP companion), planner and publisher stay on Claude. An explicit entry always beats the default, so {"implementer": "claude"} pulls implementation back host-native; "opencode" is only valid for implementer and reviewer. Returns {prUrls, tasksCompleted, escalations}; it never prompts the user mid-run.',
  phases: [
    { title: 'Implement', detail: 'rounds: implement in parallel, then one agent merges and records the round' },
    { title: 'Review', detail: 'one adherence review of the assembled work, bounded fixes, one re-entry' },
    { title: 'Ship', detail: 'ship-pr: atomic commits, push, one draft PR per changeset' },
  ],
}

// How many fix rounds the assembled review gets before its surviving findings
// are escalated, and how many times those findings may re-enter the implement
// loop as fresh tasks. Both are the run's cost ceiling -- widening them
// silently is the bug the colocated static test guards against.
const MAX_FIX_ROUNDS = 2
const SPEC_REVIEW_REENTRIES = 1
// The workable set is tracker-derived, so a node that never settles would spin
// forever; this cap turns that into a loud escalation instead.
const MAX_IMPLEMENT_ROUNDS = 25
// The workable agent call is the one place where a harness/API failure (an
// overloaded-API 529 killed two observed runs after zero work) takes the whole
// run down, so a null result -- the shape every such failure arrives in -- is
// retried with backoff. A non-null result carrying `error` is a real,
// deterministic tracker failure and is never retried.
const WORKABLE_ATTEMPTS = 3
const WORKABLE_BACKOFF_MS = [30000, 120000]
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
    `swe-loop received args as a string that is not JSON (${argsParseError}). Pass the handoff tuple {specPath, slug, containerId, baseBranch, scriptsDir, specText} as an object or as its JSON encoding.`,
  )
}

const REQUIRED_ARGS = ['specPath', 'slug', 'containerId', 'baseBranch', 'scriptsDir', 'specText']
const missing = REQUIRED_ARGS.filter(key => !ARGS || !ARGS[key])
if (missing.length) {
  throw new Error(
    `swe-loop requires args {specPath, slug, containerId, baseBranch, scriptsDir, specText} — missing: ${missing.join(', ')}. /start-loop passes the handoff tuple plus the run's integration branch, the installed plugin's scripts directory, and the spec file's text.`,
  )
}
const specPath = ARGS.specPath
// The spec's own text, read by the launcher. Any capability role may be routed
// to another provider, whose CLI runs sandboxed to the repo workspace and
// cannot open specPath -- the spec lives under docs/agents/, a symlink out of
// the repo. So the conductor carries the spec rather than naming a path only a
// host-native agent could read, and every routed prompt embeds it.
const specText = ARGS.specText
const slug = ARGS.slug
const containerId = ARGS.containerId
const baseBranch = ARGS.baseBranch
// Absolute path to the installed plugin's scripts/ dir: the target repo does
// not contain the plugin's scripts — only the plugin installation does.
const scriptsDir = ARGS.scriptsDir
if (!scriptsDir.startsWith('/')) {
  throw new Error(
    `swe-loop got a relative scriptsDir (${scriptsDir}). It must be the EXPANDED absolute path to the installed swe plugin's scripts/ dir — a value like "\${CLAUDE_PLUGIN_ROOT}/scripts" means the variable was passed through unexpanded, and the subagents' shells do not define it.`,
  )
}
// Optional, opaque: a command that prints the container's workable-issue array
// on stdout and exits non-zero on failure. The launcher resolves the tracker
// anyway, so it is the layer that knows whether the tracker's reference names a
// deterministic workable query; this file only embeds the string as data.
// Absent, the reference-driven agent query below runs unchanged.
const workableCmd = ARGS.workableCmd || null
if (workableCmd !== null && typeof workableCmd !== 'string') {
  throw new Error(
    `swe-loop got a non-string workableCmd (${JSON.stringify(ARGS.workableCmd)}). It must be a single command string that prints the workable-issue JSON array on stdout and exits non-zero on failure.`,
  )
}

// Tracker mechanics never live in this file: prompts resolve the repo's
// tracker at runtime and follow the matching to-issues reference (installed
// beside scripts/ in the same plugin), so the loop runs the same over
// whichever tracker the repo pins.
const trackerRefsDir = `${scriptsDir.replace(/\/scripts\/?$/, '')}/skills/to-issues/references`
const trackerGuide = `Tracker: resolve this repo's tracker per the to-issues skill — an "Issue tracker:" line in the repo's AGENTS.md/CLAUDE.md wins, else the skill's selection ladder — then follow the matching reference in ${trackerRefsDir}/ for every tracker operation.`

// ---- role routing -------------------------------------------------------
// The launcher may route any capability role to another provider; every other
// agent (workable query, merge, tracker bookkeeping) is loop plumbing and stays
// on the default workflow subagent. A routed role runs through that provider's
// forwarder agent, which holds only that provider's MCP tool.
const ROUTABLE_ROLES = ['planner', 'implementer', 'reviewer', 'publisher']
// Each provider names a per-role forwarder map: OpenCode pins one model per
// role at the MCP layer, so choosing the forwarder IS choosing the model, and
// it can only take a role it has a forwarder for. Routing a role it has none
// for is a launch-time stop rather than a run-time surprise.
const DELEGATORS = {
  opencode: {
    implementer: 'swe:opencode-implementer',
    reviewer: 'swe:opencode-reviewer',
  },
}
const ROLE_PROVIDERS = ['claude', ...Object.keys(DELEGATORS)]
// Where the two expensive roles run when the caller says nothing. Implementation
// and review dominate a run's token cost and are bounded enough to hand over
// whole; planning and publishing are low-token and high-side-effect, so they
// stay host-native along with every deterministic step (workable query, settle,
// tracker bookkeeping, run summary), which is never routed at all.
const DEFAULT_ROLE_PROVIDERS = { implementer: 'opencode', reviewer: 'opencode' }
const requestedRoles = ARGS.roles || {}
// Object.entries silently yields [] for a boolean or number, which would read
// as "no routing requested" and discard the caller's intent without a word.
if (typeof requestedRoles !== 'object' || Array.isArray(requestedRoles)) {
  throw new Error(
    `swe-loop got a non-object roles value (${JSON.stringify(ARGS.roles)}). Pass a map like {"implementer": "claude"} with keys among ${ROUTABLE_ROLES.join(', ')}.`,
  )
}
const delegatorFor = (role, provider) => DELEGATORS[provider]?.[role]
const invalidRoles = Object.entries(requestedRoles).filter(
  ([role, provider]) => !ROUTABLE_ROLES.includes(role) || !ROLE_PROVIDERS.includes(provider),
)
if (invalidRoles.length) {
  throw new Error(
    `swe-loop got an invalid roles map (${JSON.stringify(requestedRoles)}). Keys must be among ${ROUTABLE_ROLES.join(', ')}; values must be among ${ROLE_PROVIDERS.join(', ')}.`,
  )
}
const unsupportedRoles = Object.entries(requestedRoles).filter(
  ([role, provider]) => provider !== 'claude' && !delegatorFor(role, provider),
)
if (unsupportedRoles.length) {
  throw new Error(
    `swe-loop cannot route ${unsupportedRoles.map(([role, provider]) => `${role} to ${provider}`).join(', ')}: that provider has no forwarder agent for that role. Provider coverage: ${JSON.stringify(DELEGATORS)}.`,
  )
}
// An explicit entry always beats the default: the defaults are what an
// unopinionated run gets, never a policy the caller has to fight. Routing a
// defaulted role back to "claude" is how a caller opts out.
const roleRouting = { ...DEFAULT_ROLE_PROVIDERS, ...requestedRoles }
const agentTypeFor = role => delegatorFor(role, roleRouting[role]) ?? `swe:${role}`
// Plumbing calls carry no capability agent, so without an explicit model they
// inherit whatever model the host session happens to be running -- which is how
// one run settles a round on Fable and the next on Sonnet. These steps are
// deterministic git and tracker work whose behavior must not depend on the
// host's model picker, so the tier is pinned here and the colocated static test
// keeps every unrouted call from drifting back to "whatever the session is".
const PLUMBING_MODEL = 'sonnet'
log(`Role routing: ${ROUTABLE_ROLES.map(role => `${role}=${roleRouting[role] || 'claude'}`).join(' ')}.`)

// ---- agent contracts --------------------------------------------------------
const WORKABLE_SCHEMA = {
  type: 'object',
  required: ['issues'],
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'identifier', 'title'],
        properties: {
          id: { type: 'string' },
          identifier: { type: 'string' },
          title: { type: 'string' },
          changeset: {
            type: 'string',
            description: "the tracker's own grouping of this issue (its milestone or equivalent), '' when it has none",
          },
        },
      },
    },
    error: {
      type: 'string',
      description: 'set ONLY when the workable set could not be determined (auth, network, failed tracker query). An empty issues list means the work is genuinely drained, never that a query failed.',
    },
    topStackBranch: {
      type: 'string',
      description: "the highest-numbered stack/<n> branch that already exists for this run, or '' when there is none",
    },
  },
}

const IMPLEMENTER_SCHEMA = {
  type: 'object',
  required: ['status', 'branch', 'summary'],
  properties: {
    status: { type: 'string', enum: ['DONE', 'DONE_WITH_CONCERNS', 'NEEDS_CONTEXT', 'BLOCKED'] },
    branch: { type: 'string', description: 'the branch you committed the task to' },
    summary: { type: 'string', description: 'one paragraph: what landed and how it was verified' },
  },
}

// One review, one schema. The loop reviews the assembled branch once rather
// than reviewing each task and then re-reviewing the same lines through
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
// plus a comment agent per task cost 7M cache reads in the motivating run to
// do deterministic git and one API call each.
const SETTLE_SCHEMA = {
  type: 'object',
  required: ['results'],
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        required: ['identifier', 'merged', 'stateUpdated', 'detail', 'stackBranch'],
        properties: {
          identifier: { type: 'string' },
          merged: { type: 'boolean' },
          stackBranch: { type: 'string', description: "the stack branch this task actually landed on, '' when it did not merge" },
          stateUpdated: { type: 'boolean', description: 'whether the issue state was advanced on the tracker; cosmetic only — git, not the tracker, decides what is merged' },
          detail: { type: 'string' },
        },
      },
    },
  },
}

const SHIP_SCHEMA = {
  type: 'object',
  required: ['prUrls'],
  properties: {
    prUrls: {
      type: 'array',
      description: 'every PR opened, bottom changeset first; one entry for a single-changeset run',
      items: { type: 'string' },
    },
  },
}

// ---- prompts ----------------------------------------------------------------
const tupleFor = issueId => JSON.stringify({ specPath, slug, containerId, issueId })

// Named for provenance, embedded because a routed provider cannot open it: an
// agent that goes looking for the file spends a denied tool call and then
// reviews or implements against a guess.
const specBrief = `--- SPEC ${specPath} (verbatim below; the file itself is outside the
repo workspace and may be unreadable from your sandbox, so do not go looking
for it -- this copy is authoritative) ---
${specText}`

// Display-only shortening: log lines and escalation reasons. Never applied to
// findings handed to an agent that has to act on them.
const clip = text => String(text == null ? '' : text).replace(/\s+/g, ' ').trim().slice(0, 200)
// A changeset is a set of tasks the tracker groups together (its milestone, or
// whatever the tracker reference maps to one): one coherent story, which
// is what a reviewer holds in their head and therefore what one pull request
// should hold. It is the unit of work AND of review -- one implementer, one
// branch, one PR. A task with no changeset is a changeset of one.
const changesetsFor = issues => {
  const order = []
  const members = new Map()
  for (const issue of issues) {
    const name = String(issue.changeset || '').trim() || `\u0000${issue.identifier}`
    if (!members.has(name)) {
      members.set(name, [])
      order.push(name)
    }
    members.get(name).push(issue)
  }
  // Deliberately uncapped. A changeset too large for one implementer is a spec
  // that should have been split, and splitting it here would hide that behind
  // two half-named pull requests instead of surfacing it.
  return order.map(name => ({
    name: name.startsWith('\u0000') ? members.get(name)[0].identifier : name,
    issues: members.get(name),
  }))
}
// Every identifier stays in the branch name: it is the only tracker trace
// allowed outside the tracker, and a resumed run reads what is done from it.
const branchForChangeset = changeset => {
  const ids = changeset.issues.map(issue => issue.identifier).join('-')
  const slug = changeset.issues.length === 1 && changeset.name === changeset.issues[0].identifier
    ? ''
    : `-${changeset.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40)}`
  return `change/${ids}${slug}`
}
// The stack, bottom to top: one branch per settled changeset, each containing
// every branch below it. Its bottom is the integration branch itself, which
// keeps a one-changeset run byte-identical to the pre-stack behavior -- same
// branch, same single PR. Rounds never appear here: a round is only a
// schedule, while a changeset is the story a reviewer reads.
const stack = [baseBranch]
const stackTip = () => stack[stack.length - 1]
// stack/<n> branches an earlier session left behind. Numbering is dense by
// construction (a branch is only added once the one below it landed a changeset),
// so the highest number is the height of the stack.
const adoptStack = topStackBranch => {
  const height = Number(String(topStackBranch || '').replace(/^stack\//, ''))
  if (!Number.isInteger(height) || height < 2 || height <= stack.length) return
  while (stack.length < height) stack.push(`stack/${stack.length + 1}`)
  log(`Adopted ${stack.length} existing stack branch(es) from git: ${stack.join(' → ')}.`)
}
const numbered = items => items.map((item, i) => `${i + 1}. ${typeof item === 'string' ? item : JSON.stringify(item)}`).join('\n')

// Two shapes, one contract. A workableCmd names a command that applies the
// marker rules itself (the tracker reference that names the command is what
// guarantees it), so the agent runs it and returns its output — no per-issue
// comment reads, which were an API call per issue per round. Without one the
// agent computes the same rules through the reference.
const promptWorkable = () => workableCmd
  ? `Report this run's workable tasks as JSON.

Run EXACTLY this command with Bash and construct no other query — no
improvised tracker calls, no edits to the command, no substitutions:

    ${workableCmd}

Its stdout is this run's workable-issue array, already filtered: take each
entry as {id, identifier, title} and return them unchanged. Do not read
tracker comments and do not second-guess the list — the command has already
dropped tasks this run finished and unblocked their dependents.

Report each entry's changeset — its tracker milestone or equivalent — as "changeset",
'' when it has none: the loop hands one implementer everything sharing a changeset
instead of spawning one per issue.

Then run \`git branch --list 'stack/*'\` and report the highest-numbered
stack/<n> branch it lists as "topStackBranch" ('' if there are none). A session
resuming this run has no other record of how many dependency stack it already
opened, and merging a new task into the wrong changeset breaks the stack.

On a NON-ZERO exit put stderr verbatim in the "error" field and return an
empty issues list -- an empty list with no error means the run is finished,
so never report a failure that way.`
  : `Report this run's workable tasks as JSON.

${trackerGuide}

1. Compute the workable set of container ${containerId} per the
   reference's "swe-loop workable set" section — issues with no ready-for-human
   label that are not done and whose every blocker IS done, each as
   {id, identifier, title, changeset} — "changeset" is the issue's tracker milestone
   or equivalent, '' when it has none, and is what lets the loop hand one
   implementer a whole changeset instead of one agent per issue.
   Scripts the reference names live in ${scriptsDir}.
   If the query FAILS (auth, network, missing credential, non-zero script
   exit), put the failure text in the "error" field and return an empty issues
   list -- an empty list with no error means the run is finished, so never
   report a failure that way.
2. Run \`git branch --merged ${stackTip()}\` and read every branch it lists
   whose name begins with change/, then take EVERY issue identifier appearing
   anywhere in those names — one branch carries a whole changeset of tasks, so
   matching only change/<identifier> exactly under-reports what is done. Those
   tasks are merged into this run's topmost
   dependency changeset, which contains every changeset below it and is therefore what
   "done in this run" means — their tracker
   state does not advance until the run's PR lands, so never judge it from the
   tracker alone.
3. An issue counts as DONE when its tracker state is closed OR its identifier
   appears in that merged list. Drop a done issue, and treat a done blocker as
   satisfied rather than as still blocking. Skipping the second half is what
   makes a dependency chain stall after its first task.
4. Run \`git branch --list 'stack/*'\` and report the highest-numbered
   stack/<n> branch it lists as "topStackBranch" ('' if there are none). A session
   resuming this run has no other record of how many stack branches it
   already opened, and merging a changeset onto the wrong one breaks the
   stack.
5. Return the surviving issues.`

const promptImplementer = (changeset, from) => `Execute this bounded assignment: implement ${changeset.issues.length === 1 ? 'one task' : `${changeset.issues.length} related tasks`} of ${specPath}, end to end.

Handoff tuple: ${tupleFor(changeset.issues.map(issue => issue.id))}
${changeset.issues.length === 1 ? `Task: ${changeset.issues[0].identifier} — ${changeset.issues[0].title}` : `Changeset "${changeset.name}", to be implemented in one pass because these tasks
share a concern and will be reviewed as one pull request:
${numbered(changeset.issues.map(issue => `${issue.identifier} — ${issue.title}`))}`}

1. Create or check out branch ${branchForChangeset(changeset)} from ${from} and work
   only there — on a resumed or retried task the branch may already exist,
   with earlier commits on it.
2. Implement ${changeset.issues.length === 1 ? 'the task' : 'each task, in the order listed'} per the implement skill's per-task
   discipline: prove the behavior first (tdd), then lint, types, tests.
   ${changeset.issues.length === 1 ? '' : `Commit each task separately, so the pull request this branch becomes reads
   as one coherent change per commit. A task you cannot finish does not sink
   the rest: implement the others and name it in your summary.`}
3. COMMIT the work to ${branchForChangeset(changeset)}. Do not push, do not merge, do
   not open a PR — the conductor merges and ships.
4. Report {status, branch, summary}; "branch" is the branch you actually
   committed to. NEEDS_CONTEXT or BLOCKED means you could not finish: name
   exactly what is missing instead of guessing.

Do not touch the tracker: the run records each task's outcome itself once the
changeset merges, and your summary is what it records. Nothing moves on the
tracker until work is merged, so there is no state for you to set here.

${specBrief}`

const promptReview = () => `Review the assembled implementation against its spec, through one lens:
does the code do what the spec asked, correctly?

Under review: the complete work of this run, which lives on ${stackTip()} —
the top of the run's dependency stack, containing every changeset below it.
Establish the diff yourself — the task merges are on the changeset branches and
each changeset carries a change/<identifiers> branch — and say in your first finding
if you could not establish it rather than reviewing a guess.
Spec: ${specPath}

This is the run's ONLY code review, so judge adherence end to end: behavior the
spec asked for and the code lacks, behavior that diverges from what the spec
asked, and missing tests for either. Task branches were already gated on their
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
would act on it.

${specBrief}`

const promptFixer = (findings, round) => `Execute this bounded assignment: apply review findings.

Findings to resolve (fix round ${round}/${MAX_FIX_ROUNDS}):
${numbered(findings)}

Work in the main worktree at the repo root.
${stack.length === 1
  ? `Work directly on ${baseBranch} — the tasks are already merged there.`
  : `This run landed in ${stack.length} dependency stack, bottom to top:
${numbered(stack)}
Every finding opens with a file:line anchor. Fix it on the LOWEST changeset that
contains the code it names — \`git log <changeset> -- <file>\` says which changeset
introduced the line — never on the top changeset by default: a fix committed above
the layer that owns it lands in the wrong pull request. After committing on a
changeset below the top, replay the stack above it so they carry the fix, in order:
\`git checkout <higher changeset> && git rebase <the changeset directly below it>\`. On
conflict, read what each side was trying to do before choosing — keep both
intents where they can coexist, and never resolve by taking one side wholesale
— then re-run the project's checks and continue the rebase.
Nothing is published yet, so these rebases rewrite local branches only.`}
Apply every finding, re-run lint/types/tests, and commit. Do not push and do not
merge. Return a concise completion note; this call has no additional output
schema.

${specBrief}`

const promptEscalationNote = (issue, reason) => `Post one comment on tracker issue ${issue.identifier}.

${trackerGuide}

The comment body is exactly:

**swe-loop escalation** — ${clip(reason)}

Post nothing else and change no issue fields.`

const promptSettle = plan => `Settle this round's finished changesets, in the main worktree at the repo root.
Work through them IN THE ORDER GIVEN, one at a time.

${trackerGuide}

Each changeset lands on its OWN stack branch, stacked on the branch below it: a
changeset is one coherent story and becomes one pull request, so putting two on one
branch is what makes a diff unreviewable. The branches nest — each contains
every branch below it — which is what lets each pull request base on the last.

Changesets:
${numbered(plan.map(entry => `${entry.branch} → stack branch ${entry.target}${entry.target === entry.from ? '' : `, created from ${entry.from}`} (${entry.issues.map(issue => issue.identifier).join(', ')})`))}

For each changeset, in order:
1. Check out its stack branch, creating it from the branch named above if it
   does not exist yet (git checkout -b <target> <from>). Never cut a stack
   branch from the default branch — it would drop every changeset below it.
2. git merge --no-ff <the changeset branch>
3. On conflict, resolve it per the merge-conflicts skill and complete the merge.
   If you cannot resolve it confidently, git merge --abort, record merged:false
   with the reason, and move on — never force a resolution you are unsure of
   and never abandon the remaining changesets. A changeset that fails leaves its stack
   branch uncreated, so settle the NEXT changeset onto the last stack branch that
   did succeed (or ${plan[0].from} if none has).
4. Only after its merge succeeds, advance each of that changeset's issues to
   "in review" per the tracker reference's state-transition section, and post
   one comment with its one-line summary. Record stateUpdated:true only if the
   state write actually succeeded.

Return one {identifier, merged, stateUpdated, detail, stackBranch} per TASK —
every task of every changeset, in the order listed. "stackBranch" is the branch
that task actually landed on, '' when it did not merge; the conductor builds
the stack from what you report, so a branch you renamed or skipped must be
reported as you left it. Do not push. The state write is for humans reading the
tracker: a resumed run decides what is already merged from git, so a failed
state write never loses or repeats work.`

const promptFileFindings = findings => `File surviving review findings as fix tasks in tracker container ${containerId}.

Spec: ${specPath}
Findings:
${numbered(findings)}

One issue per finding that needs code. Write bodies against the to-issues
issue template and check each with
   uv run ${scriptsDir}/validate_artifacts.py issue -
(body on stdin) before publishing. Do not re-file a finding that already has
an open issue in the container.`

const promptShip = () => stack.length === 1
  ? `Ship the finished work on ${baseBranch}.

Handoff tuple: ${tupleFor(null)}

Run the ship-pr skill: verify lint/types/tests, changeset any uncommitted work into
atomic commits, push ${baseBranch}, and open a DRAFT pull request. Tracker
links, issue ids, and tracker-only content never appear in commit messages, the
PR title, or the PR body. Return the PR URL as the one entry of prUrls.`
  : `Ship this run's work as a STACKED pull request — it landed in
${stack.length} dependency stack, bottom to top:
${numbered(stack)}
Each changeset branch contains every changeset below it, so ${stackTip()} holds the
complete work.

Handoff tuple: ${tupleFor(null)}

Run the ship-pr skill in STACK MODE: verify lint/types/tests, changeset any
uncommitted work into atomic commits on the changeset that owns it, then publish the
stack in the order listed above as one DRAFT pull request per changeset, each based
on the changeset below it and each with a body that stands on its own. The skill
names the exact commands, and the fallback for a host where stacked pull
requests are unavailable — do not improvise a substitute.

Tracker links, issue ids, and tracker-only content never appear in commit
messages, PR titles, or PR bodies. Return every PR URL in prUrls, bottom changeset
first.`

const promptRunSummary = summary => `Post this run's summary as one comment on tracker container ${containerId},
per the tracker reference's container-comment convention.

${trackerGuide}

Run: ${slug} — spec ${specPath}, integration branch ${baseBranch},
dependency stack ${stack.join(' → ')}.

The comment body is a short "swe-loop run summary" heading followed by this
payload verbatim in a fenced json block:

${JSON.stringify(summary, null, 2)}

Then reconcile the container's own status with its issues per the tracker
reference's state-transition section: a container still reading "backlog" or
"planned" while its issues are underway is the drift this step exists to
correct. Never mark the container complete — this run ends at a draft PR, not
a merge.`

// ---- run state --------------------------------------------------------------
const tasksCompleted = []
const escalations = []
// Issues settled (merged or escalated) earlier in THIS run. The tracker cannot
// tell us about them yet -- their state only advances when the PR lands.
const settled = new Set()

const escalateRun = (title, reason, details = []) => {
  escalations.push({ issue: null, title, reason, findings: details })
  log(`ESCALATED ${title}: ${reason}`)
}

// A task escalates only when it could not be implemented or merged, so this
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
    model: PLUMBING_MODEL,
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

const finish = async prUrls => {
  const summary = { prUrls, tasksCompleted, escalations }
  const posted = await agent(promptRunSummary(summary), {
    label: `run-summary:${slug}`,
    model: PLUMBING_MODEL,
    phase: 'Ship',
    effort: 'low',
  })
  if (!posted) log('Run-summary comment did not post — the returned summary is the only record of this run.')
  return summary
}

// ---- Implement --------------------------------------------------------------
// Splitting is the launcher's job: /start-loop publishes the tasks (or aligns
// pre-existing tracker issues to the spec) before launching, so the run's
// first act is asking the tracker what is workable.
// Null means the agent call itself died (harness or API), which is transient;
// retry it with backoff. Anything non-null -- including a result carrying
// `error` -- is the tracker's own answer and is returned to the caller as-is.
const requestWorkable = async label => {
  for (let attempt = 1; attempt <= WORKABLE_ATTEMPTS; attempt += 1) {
    const workable = await agent(promptWorkable(), {
      label: attempt === 1 ? label : `${label}:retry${attempt - 1}`,
      model: PLUMBING_MODEL,
      phase: 'Implement',
      effort: 'low',
      schema: WORKABLE_SCHEMA,
    })
    if (workable) return workable
    if (attempt === WORKABLE_ATTEMPTS) return null
    const wait = WORKABLE_BACKOFF_MS[attempt - 1]
    log(`Workable query attempt ${attempt}/${WORKABLE_ATTEMPTS} returned nothing — retrying in ${wait / 1000}s.`)
    await new Promise(resolve => setTimeout(resolve, wait))
  }
  return null
}

const runImplementLoop = async passLabel => {
  phase('Implement')
  for (let round = 1; round <= MAX_IMPLEMENT_ROUNDS; round += 1) {
    const workable = await requestWorkable(`workable:${passLabel}:${round}`)
    if (!workable || workable.error) {
      // Verbatim and unclipped: this reason is the only record of what actually
      // failed, and a truncated 529 or GraphQL error reads as a mystery.
      const reason = workable
        ? String(workable.error)
        : `workable query returned nothing after ${WORKABLE_ATTEMPTS} attempts`
      escalateRun('workable query', AUTH_ERROR_SIGNATURE.test(reason) ? `${reason}${AUTH_HINT}` : reason)
      log(`Workable query failed (${reason}) — stopping the ${passLabel} loop rather than reading it as finished work.`)
      return
    }
    // A cold resume (no resumeFromRunId) starts with stack = [baseBranch] and
    // would settle round 1 straight into changeset 1, on top of layers a previous
    // session already opened. git is the only record of them.
    adoptStack(workable.topStackBranch)
    const pending = (workable.issues || []).filter(issue => !settled.has(issue.id))
    if (!pending.length) {
      log(`Workable set drained on round ${round} of the ${passLabel} loop.`)
      return
    }
    log(`Round ${round} (${passLabel}): ${pending.length} task(s) — ${pending.map(issue => issue.identifier).join(', ')}`)

    // Implement only. A task's gate is its own lint/types/tests, which the
    // implementer runs and which cost no tokens; the code is reviewed once,
    // assembled, after the loop drains.
    // Batching happens before the fan-out, not after: a subagent costs its whole
    // context load plus a worktree plus a merge before it edits a line, so
    // parallelising two five-line fixes costs more than doing both in one.
    const changesets = changesetsFor(pending)
    log(`Round ${round}: ${pending.length} task(s) in ${changesets.length} changeset(es) — ${changesets.map(changeset => `${changeset.name} (${changeset.issues.length})`).join(', ')}.`)
    const from = stackTip()
    const outcomes = await parallel(
      changesets.map(changeset => async () => {
        const result = await agent(promptImplementer(changeset, from), {
          label: `implement:${changeset.name}`,
          phase: 'Implement',
          agentType: agentTypeFor('implementer'),
          isolation: 'worktree',
          schema: IMPLEMENTER_SCHEMA,
        })
        const fail = async reason => {
          for (const issue of changeset.issues) await escalate(issue, reason)
          return null
        }
        if (!result) return await fail('implementer returned no result (skipped or errored)')
        if (result.status === 'NEEDS_CONTEXT' || result.status === 'BLOCKED') {
          return await fail(`implementer reported ${result.status}: ${clip(result.summary)}`)
        }
        const branch = result.branch || branchForChangeset(changeset)
        log(`${changeset.name}: implemented (${result.status}) on ${branch}.`)
        return { changeset, state: 'implemented', summary: result.summary, branch }
      }),
    )

    // One agent merges the whole round in order and marks each task as it
    // lands: merges must be sequential anyway (two agents merging into the
    // same working copy race on the index), so per-task merge and marker
    // agents bought nothing but their own context.
    const ready = outcomes.filter(Boolean).filter(outcome => outcome.state === 'implemented')
    let merged = 0
    if (ready.length) {
      // One changeset per changeset, chained in settle order. Named up front so the
      // agent chains deterministically; read back from its report, because a
      // changeset that fails to merge leaves its changeset uncreated.
      let tip = from
      let height = stack.length
      let landed = tasksCompleted.length > 0 || height > 1
      const plan = ready.map(outcome => {
        const target = landed ? `stack/${height + 1}` : baseBranch
        const entry = { branch: outcome.branch, issues: outcome.changeset.issues, from: tip, target }
        if (target !== tip) height += 1
        tip = target
        landed = true
        return entry
      })
      const settlement = await agent(promptSettle(plan), {
        label: `settle:${passLabel}:${round}`,
        model: PLUMBING_MODEL,
        phase: 'Implement',
        schema: SETTLE_SCHEMA,
      })
      const results = settlement ? settlement.results || [] : []
      for (const issue of ready.flatMap(outcome => outcome.changeset.issues)) {
        const result = results.find(entry => entry.identifier === issue.identifier)
        if (!result || !result.merged) {
          await escalate(issue, `merge failed: ${result ? clip(result.detail) : 'the settle agent reported nothing for this task'}`)
          continue
        }
        settled.add(issue.id)
        tasksCompleted.push(issue.identifier)
        merged += 1
        if (result.stackBranch && !stack.includes(result.stackBranch)) {
          stack.push(result.stackBranch)
          log(`Stack height ${stack.length}: ${result.stackBranch}.`)
        }
        log(`${issue.identifier}: merged into ${result.stackBranch || baseBranch}.`)
        // A failed state write is cosmetic and never escalates: the merge is in
        // git, which is what a resumed run reads. This used to be an escalation
        // because a missing marker really could lose or repeat a task.
        if (!result.stateUpdated) {
          log(`${issue.identifier}: merged, but its tracker state did not advance — the tracker under-reports this task.`)
        }
      }
    }
    // Anything the pipeline dropped (null outcome, unknown state) would come
    // back on the next workable query and be re-spawned forever; settle it.
    for (const issue of pending) {
      if (settled.has(issue.id)) continue
      await escalate(issue, 'the implement pipeline produced no settled outcome for this task')
    }
    log(`Round ${round} (${passLabel}) summary: ${merged} merged, ${pending.length - merged} escalated, ${escalations.length} escalation(s) so far.`)
  }
  log(`Implement loop hit its ${MAX_IMPLEMENT_ROUNDS}-round cap without draining — stopping and escalating.`)
  escalateRun('implement loop', `hit the ${MAX_IMPLEMENT_ROUNDS}-round cap; tasks remain unworked`)
}

await runImplementLoop('implement')

// Reviewing and shipping an unimplemented base branch burns high-tier agents on
// nothing and can open a PR over an empty diff; stop at the summary instead.
if (!tasksCompleted.length && escalations.length) {
  log(`No task merged into ${baseBranch} and ${escalations.length} escalation(s) stand — skipping review and ship.`)
  return await finish([])
}

// ---- Review -----------------------------------------------------------------
// One review of the assembled work, then bounded fixes against it. Findings
// are fixed in place on the integration branch: re-splitting them onto the
// tracker and re-entering the implement loop costs a planner, a workable query,
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
  log(`${openFindings.length} finding(s) survived ${MAX_FIX_ROUNDS} fix rounds — filing them as tasks (re-entry ${reentries}/${SPEC_REVIEW_REENTRIES}).`)
  const filed = await agent(promptFileFindings(openFindings), {
    label: `file-findings:${reentries}`,
    phase: 'Review',
    agentType: agentTypeFor('planner'),
  })
  if (!filed) {
    log('Could not file the findings as fix tasks — collecting them as escalations instead.')
    break
  }
  await runImplementLoop(`review-${reentries}`)
  phase('Review')
  openFindings = await settleFindings(`-r${reentries}`)
}
if (openFindings.length) {
  escalateRun(
    `${openFindings.length} finding(s) survived review`,
    `${openFindings.length} finding(s) survived ${MAX_FIX_ROUNDS} fix rounds on ${stackTip()}`,
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
  escalateRun('ship-pr', `publisher returned no PR URL; ${stackTip()} is merged but unpublished`)
  log(`Ship failed — ${stackTip()} holds the merged work but no PR was opened.`)
} else {
  log(`Draft PR(s): ${(shipped.prUrls || []).join(', ')}`)
}

return await finish(shipped ? shipped.prUrls || [] : [])
