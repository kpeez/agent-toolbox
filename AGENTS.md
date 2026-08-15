# Agent instructions

## Principles

- Work to the requested scope. Preserve unrelated working-tree changes.
- "Done" means the relevant verification ran. Report failures as failures.
- Do not end with unsolicited offers of more work.
- Do not commit, push, open a pull request, or change external state unless the
  user asked for it.

## Communication

- Use plain, direct language and active voice.
- Keep sentences short. Put one idea in each sentence.
- Use the same term for the same idea.
- Avoid idioms, slang, filler, and unexplained jargon.
- State the conclusion first. Support factual claims with evidence. Cite the
  source or file location.
- Keep paragraphs under six sentences.

## Orchestration

- Keep the primary agent focused on requirements, decisions, task design,
  synthesis, review, and final verification.
- The primary agent may directly perform targeted reads, quick directory
  checks, and small obvious edits.
- Delegate extensive exploration, research, review, and log analysis.
- Delegate the bulk of any non-obvious implementation or detailed writing. Use
  the smallest capable agent.
- Before delegation, inspect enough context to write a complete handoff. Include
  the goal, relevant context, exact scope, file ownership, constraints,
  acceptance criteria, and required checks.
- Require subagents to preserve unrelated work and return a concise summary,
  changed files, verification evidence, and unresolved concerns.
- Review the result and run the final relevant checks in the primary session.
  Do not treat a subagent report as verification.
- Do not run parallel writes without isolated worktrees or disjoint file
  ownership.
- If delegation is unavailable, report that limitation before doing substantial
  work in the primary context.

## Workflow

1. Read the repository instructions and README; inspect existing patterns before
   changing behavior.
2. For non-trivial work, clarify the design, write an approved spec, and split it
   into tracker issues before implementation. Specs and durable agent context live
   under the gitignored `docs/agents/` symlink.
3. Implement one bounded task at a time: prove the intended behavior, then run
   lint, type checks, and relevant tests. Fix failures before declaring success.
4. Run a host-native review before publication. Publish through the repository's
   release workflow only when authorized.

## Code rules

- Prefer the smallest clear change. Do not add abstraction, flexibility, or error
  handling the request does not need.
- Keep code flat and local; use descriptive names and required types.
- Remove only orphaned code created by your own change. Use `trash`, not `rm`, for
  recoverable deletions.
