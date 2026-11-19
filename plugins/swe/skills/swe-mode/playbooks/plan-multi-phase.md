# plan-multi-phase

Applies when: work that spans phases or stacked PRs needs a plan an owner runs box by box.

You own the plan, not the code. The plan is a checklist an owner runs box by box and the user audits from the evidence. The plan is the deliverable. Do not implement.

1-skip-small-change: When the change is one or two files with an obvious approach and the user did not ask for a plan or a checklist, skip the plan. Say so and stop.
2-settle-by-prototype: Settle open questions by prototype before you write. Settle a product or preference call no run can settle with interview-user. (build-prototype, interview-user)
3-write-plan-file: Write the plan's HTML source where [plan storage](../../../references/plan-storage.md) puts it: `.agents/docs/plans/<slug>.plan.src.html` when the project has a `.agents/docs` folder, else `.agents/scratch/<branch-slug>/`. Open with what changes, the PR ids in landing order, and the dependency graph: which PRs are independent and branch from trunk, which wait for which, and the files each may touch. Then one section per PR, with checkboxes for what it depends on, the files it edits, the one change it builds, the result you see, and its verification. (sequence-verifiable-units, writing)
4-require-real-verification: Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Each live box drives the real surface with a concrete scenario and a pass predicate. The perf box names the metric, the probe, the trunk baseline measured first, and the number that fails. A PR that changes an interaction waits for the user's review before merge. (prove-it-works)
5-hand-back: Hand back the plan path and stop. Execution starts on the user's explicit go.

Reply: the plan path, the PR ids with their dependencies and the review-gated set, and what stays unproven. No PR.
