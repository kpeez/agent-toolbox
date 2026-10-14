# author-skill

Applies when: write or edit a skill, `AGENTS.md`, or `CLAUDE.md`.

You own the skill's voice.

When in doubt, delete. Keep only prose that changes a decision. Tell the agent to do the thing and skip the reason unless the rule is confusing without one. Match tone to scope. Delegate to other skills by path. When a workflow keeps recurring and no skill captures it, propose a new skill.

1-choose-invocation: Choose model-invoked, model-only, or user-invoked and say why. (writing-for-agents)
2-single-source-check: Point to the existing home of any rule, or to a structural source such as a type, README, or config, instead of restating it. (writing-for-agents, encode-lessons-in-structure)
3-cut-to-decisions: Delete each sentence that changes no decision. (writing-for-agents, unslop)
4-validate-skill: Check that frontmatter has `name` and `description`, referenced files exist, and cross-skill links resolve.
5-check-packaging: Apply the packaging rules and run the checks that the repository's AGENTS.md names for the changed files.
6-plan-activation-check: When the change is structural or a model-invoked description changes, add or update a test case. Skip for a subjective change. (evaluate-agent-change)
7-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: a summary of the skill, the key design decisions, its always-on character cost, and the validation and checks run.
