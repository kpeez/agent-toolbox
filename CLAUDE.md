# Agent instructions

This is the provider-neutral source of truth. `AGENTS.md` is a symlink to this
file; `scripts/install.sh` copies it to supported hosts. Keep repository-specific
commands and conventions in that repository's own instructions, not here.

## Principles

- Work to the requested scope. Preserve unrelated working-tree changes.
- "Done" means the relevant verification ran. Report failures as failures.
- Do not end with unsolicited offers of more work.
- Do not commit, push, open a pull request, or change external state unless the
  user asked for it.

## Workflow

1. Read the repository instructions and README; inspect existing patterns before
   changing behavior.
2. For non-trivial work, clarify the design, write an approved spec, and split it
   into tracker issues before implementation. Specs and durable agent context live
   under the gitignored `docs/agents/` symlink.
3. The tracker owns task and implementation status. Do not create or consult a
   local `STATUS.md` workflow.
4. Implement one bounded task at a time: prove the intended behavior, then run
   lint, type checks, and relevant tests. Fix failures before declaring success.
5. Run a host-native review before publication. Publish through the repository's
   release workflow only when authorized.

## Code rules

- Prefer the smallest clear change. Do not add abstraction, flexibility, or error
  handling the request does not need.
- Keep code flat and local; use descriptive names and required types.
- State assumptions when they affect the design. Escalate material choices rather
  than silently deciding them.
- Remove only orphaned code created by your own change. Use `trash`, not `rm`, for
  recoverable deletions.
