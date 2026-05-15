# AGENTS.md

## Priority

This file > README.md > in-code comments. Closest AGENTS.md wins in
subdirectories.

## Workflow

1. Read this file and README.md
2. Check `specs/` for feature specs — read AGENTS.md + STATUS.md before
   working
3. Inspect existing patterns before adding new ones
4. Implement → lint → types → tests
5. Verify: run examples and update logs, fix failures first
6. After changing any per-spec STATUS.md, regenerate specs/STATUS.md with the
   spec status script

> For non-trivial features, create a spec first with `/spec new <name>`.

## Verification

"Done" means "ran it." Example failures = spec failures.

## Workflow Permissions

- Use auto-approval execution by default for normal implementation, lint,
  typecheck, test, and documentation work.
- Keep filesystem access bounded to the workspace and provider-approved writable
  roots when the provider supports it.
- Permission-gate or deny destructive command families that can destroy
  pre-existing work: `rm`, `rmdir`, `git clean`, `git reset --hard`, recursive
  `chmod`/`chown`, `rsync --delete`, `sudo`, `dd`, and disk erase commands.
- Clean up files or folders created during the current session when they are no
  longer needed. Generated caches created by the current session, such as
  `__pycache__/`, `.pytest_cache/`, and tool cache folders, may be removed as
  routine cleanup.
- Avoid verification commands that create Python bytecode caches unless the
  cache files are the thing being tested. Prefer `PYTHONDONTWRITEBYTECODE=1`
  for ad hoc Python checks.
- Apply this permission model consistently across Claude Code, Codex CLI,
  Gemini CLI, and GitHub Copilot CLI installations.

## Authorship

- Never add agent attribution to commits or PRs. Do not add `Co-authored-by`,
  `Signed-off-by`, `Generated with`, AI tool signatures, agent names, or agent
  entries in contributors lists. Commit and PR authorship belongs only to the
  human user.

## GitHub Workflow

- Prefer atomic PRs. A spec can produce multiple PRs; do not assume one spec
  maps to one PR.
- Use small, logical commits with imperative, conventional-style subjects.
- Generate PR titles and bodies directly from PLAN.md, SPEC.md, STATUS.md,
  linked issues, and the actual diff. Do not create `commits.md` or
  `draft-pr.md` review artifacts.
- Use squash merge by default. Do not create merge commits unless the user
  explicitly asks for one.
- After a PR merges, update the relevant STATUS.md with PR number, merge or
  squash commit SHA, and a short note about what shipped.
- Regenerate specs/STATUS.md after updating STATUS.md. Local git hooks may do
  this as a safety net, but remote GitHub PR events do not run local hooks.

## Code Rules

### Think first

- State assumptions. Ask when uncertain. Push back when simpler approaches
  exist.

### Simplicity

- No abstractions, flexibility, or error handling beyond what was asked
- If 200 lines could be 50, rewrite it
- Inline unless reused. Colocate related logic. Keep functions flat (early
  returns, one indent level).

### Surgical changes

- Only touch what the request requires. Match existing style.
- Remove orphans YOUR changes created. Don't touch pre-existing dead code.

### Types and state

- Required over optional. Minimize arguments. Const by default.
- Discriminated unions over loose types. Exhaustive handling; fail on unknown.
- Assert shape on inputs — no silent defaults. Trust the type system.

### Goal-driven development

Every task follows a red/green cycle — define a verifiable goal before writing
code, then loop until verified.

### Style

- Descriptive names (`is_active`, `has_permission`). Comments only for why.
- Reuse helpers. Named constants. Fail fast. No slop.
- Small commits, imperative messages. Lint, types, and tests pass before PR.
