# run-program

Applies when: a standing project handed to one coordinator session, multi-day, with many stacked PRs, many subagents, and few human turns ("run this whole project", "own this migration until it lands").

You own the program, never the code. Author briefs, drain the queue, keep the frontier green, and decide.

Route here only when the work outlives any single agent. One task driven to a predicate is run-autonomously. One ambitious run that needs a bespoke workflow is figure-it-out. Work one agent could finish inside the session's budget is not a program. The roles, store, brief, drain, stack safety, verification, failure, and escalation rules live in [program rules](../references/run-program.md).

1-frame-program: State the done predicate as a count, such as all 126 units merged and each ledger-verified `unit-test-verified` or better. Quantify units, effort, stacks, and the wall-clock budget. When one agent could finish inside the budget, run run-autonomously instead, with no store. By about 70 percent of the budget, stop spawning and land what is verified. Settle a contested decomposition or one-way door with competing candidates before the pilot. Present the framing once. (run-autonomously, swarm)
2-install-store: Create the store files, open the decision log, write the standing orders before any spawn, and seed `frontier.json` from existing PRs. (log-decisions)
3-run-pilot: Push one unit through the whole path, brief, worker, verification, stack entry, ledger row, and merge, to falsify the brief, the verify recipe, and the unit size. Fix the contract from its evidence before fan-out. For near-identical cheap units, the first unit is the pilot. (sequence-verifiable-units)
4-scale-rolling-window: Spawn a rolling window of workers up to the in-flight cap and refill as children finish. Add track sub-coordinators only past the one-drain threshold. Relay upstream reports into downstream briefs. Keep sibling communication upward. (orchestrate, guard-the-context-window)
5-drain-queue: Run the queue and drain discipline at every drain point.
6-land-continuously: Land from the first verified unit on, alongside the remaining waves. Keep the frontier green before upper-stack work, and advance `frontier.json` only on a merge or a reported new head SHA. (babysit-pr, ship-stack)
7-close-program: Drain the final inbox, reconcile every spawned agent to a terminal row, confirm the predicate on the real artifact, and confirm each landed PR has a verdict for its head SHA. Audit the decision log, encode recurring corrections into `preferences.md` or the brief, and leave the store intact as the postmortem. (prove-it-works, log-decisions, encode-lessons-in-structure)

Reply: at checkpoints and at close, the predicate and the count against it from `units.tsv` and `ledger.tsv`, tracks and what each landed, the frontier (PR list plus SHAs), a verdict summary, what was abandoned and why, gates awaiting the human (the only asks), the store path, and the decision log path, with PR links. Numbers come from the tables, not narrative.
