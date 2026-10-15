# pick-up-session

Applies when: resuming or taking over a prior agent's in-flight work from a handoff file, a decision log, a session transcript, a cloud session, or a pushed branch.

You own the resume point. Read the prior trail; do not redo it.

1-locate-prior-trail: Read the work's handoff file and its decision log first. Then use a session transcript of this project only (Claude Code `~/.claude/projects/<project-slug>/*.jsonl`, Codex `~/.codex/sessions/`), a cloud session, or a pushed branch. Never read transcripts of unrelated projects. Read the last messages, then scan back for the decision points. Parse a long transcript in a subagent and keep only the reduced timeline. (handoff, log-decisions, recall, guard-the-context-window)
2-reconstruct-state: Reconstruct the branch and worktree, what already landed (`git log`, `git diff` against the base), the open todos, and the decisions made. The prior trail is authoritative input. Do not re-derive it.
3-diff-done-vs-pending: Compare what shipped against what was planned and name the resume point. Do not rerun the prior repro or redo completed work. A "verify from scratch" pass treats an authoritative trail as untrustworthy.
4-route-remaining-work: Route the remaining work to the matching playbook and pick one verdict. Continue the execution, ship a finished recommendation, ratify or override a prior conclusion, or postmortem a failed run. The routed playbook owns the rest.
5-verify-inherited-claims: Verify the inherited claims against the original goal on the real artifact. A passing prior self-report is not proof. (prove-it-works)

Reply: where the prior agent stopped, what you inherited versus redid (ideally nothing redone), the resume point, and the outcome.
