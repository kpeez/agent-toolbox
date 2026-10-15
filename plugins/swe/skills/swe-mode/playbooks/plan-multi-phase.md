# plan-multi-phase

Applies when: work that spans phases or stacked PRs needs a plan an owner runs box by box.

You own the plan, not the code. The plan is a checklist an owner runs box by box and the operator audits from the evidence.

The plan is the deliverable. Do not implement. The verification rule, the verification surface, and the plan skeleton live in [plan-multi-phase rules](../references/plan-multi-phase.md).

1-skip-small-change: When the change is one or two files with an obvious approach, skip the plan. Say so and stop.
2-settle-by-prototype: Settle each open question by a prototype before you write, and keep its branch, SHA, and screenshots for Appendix A. Settle a product or preference call no run can settle with interview-user. (build-prototype, never-block-on-the-human, interview-user)
3-explore-in-subagents: Explore in subagents. Each returns file pointers, conventions, test commands, and entry points, not inlined dumps. (guard-the-context-window)
4-fill-skeleton: Copy the skeleton into the plan file in the plans directory and fill every placeholder, with one section per PR. Name the execution playbook in How to read this, autopilot-full or autopilot-stack by the rule in autopilot-stack, or run-program for a standing program. (sequence-verifiable-units)
5-write-as-how-to: Write the body as one how-to. Appendices hold explanation and reference. Each heading states the task or the finding. No long dashes and no mid-sentence colons. (writing)
6-run-plan-check: Run `python3 <plugin-root>/scripts/check_plan.py <plan.md>` ([check_plan.py](../../../scripts/check_plan.py)) and fix every line it prints. (encode-lessons-in-structure)
7-hand-back: Post the plan path and the check output, then stop. Execution starts on the operator's explicit go, under the playbook the plan names.

Reply: the plan path, the PR ids with their dependencies and the review-gated set, what the prototypes proved and what stays unproven, and the check output. No PR.
