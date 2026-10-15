# Make it yours

This page shows how you adapt swe to your own projects and habits. It covers lessons from one session, fixes that stop a repeated mistake, new skills, tests for a skill change, and your own fork of the plugin.

Start smaller than you think. You do not need many skills on day one. Prompt plainly, watch where agents fail, and add a skill or a check when the same failure comes up a second time.

## Capture a session's lessons with reflect

Right after a task that taught you something, type this:

```text
/swe:reflect that took too long. capture what we learned so the next run doesn't repeat it.
```

[reflect](../skills/reflect/SKILL.md) is user-invoked, so it runs only when you type it. It finds this session's transcript and reads only this project's transcripts. Then it starts three reviewers in parallel, each with a different lens (judgment, tooling, and divergent). A fourth subagent synthesizes their findings into Accepted, Rejected, and Backlog lists.

reflect moves to Backlog each finding that a lint, script, type, or check would enforce better than prose. It waits for your approval before it applies any skill edit. Approve a finding only if it would change a future decision. One strange session is an anecdote, not a rule.

## Fix the repository with correct

When you correct agents for the same mistake again and again, the fix belongs in the repository, not in your next prompt. [correct](../skills/correct/SKILL.md) fixes each mistake class at the highest level that works:

1. `architecture` removes the mistake. One owner per piece of state, one supported path per task, and no dead code for an agent to copy.
2. `types` make the bad state impossible to write.
3. `lint-or-check` fails the build with an error that names what to use instead.
4. `test` checks the behavior.
5. `docs-last` writes a doc or agent rule, only for a judgment call. Nothing fails when an agent skips a doc.

```text
/swe:correct agents keep calling the database client directly instead of going through the repository layer
```

correct reads the current correction, recent commits and reverts, review comments, and comments that explain workarounds. It groups the mistakes into classes. A class counts at its second occurrence. It fixes the most frequent classes first, one commit per class. It proves that each new enforcer fails on a real past mistake and passes on the fix. When a structural fix works, it removes the instruction that the fix replaces.

correct also keeps a rule-to-enforcer table. In this repository the table is [docs/agent-rule-enforcers.md](../../../docs/agent-rule-enforcers.md), and a line in `AGENTS.md` points to it. Each row names the rule, the past mistakes, the level, the enforcer, and the command that runs it. When you correct a mistake whose rule is already in the table, correct checks that the enforcer still exists and still fails. An enforcer that stopped working counts as a repeat, so the fix moves to a higher level. In a project with no table, correct creates one in a docs file and adds one `AGENTS.md` line that points to it.

reflect and correct split the work. reflect improves skills from one session. correct changes the repository so that a mistake class cannot come back.

## Author a skill through the playbook

When you know the workflow you want to capture, give it to the router:

```text
/swe:swe-mode write a skill for verifying database migrations in this repo
```

The router matches the [author-skill](../skills/swe-mode/playbooks/author-skill.md) playbook. It also matches an edit to `AGENTS.md` or `CLAUDE.md`. Its steps choose the invocation mode, point to the existing home of each rule instead of restating it, cut each sentence that changes no decision, check frontmatter and links, run the repository's packaging checks, and update the draft PR. The reply states the skill's always-on context cost.

The steps load [writing-for-agents](../skills/writing-for-agents/SKILL.md). Agent-facing prose has a higher bar than prose for people, because each sentence becomes an instruction some future agent follows. Its [skill mechanics](../skills/writing-for-agents/SKILL-MECHANICS.md) page sets the invocation mode by who must start the skill:

| Mode | Who starts it | Frontmatter |
| --- | --- | --- |
| Model-invoked | You or the agent | No switch |
| Model-only | Only the agent or another skill | `user-invocable: false` |
| User-invoked | Only you | `disable-model-invocation: true` |

Codex ignores `disable-model-invocation`. A user-invoked skill also needs `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.

A skill you type with input also sets `argument-hint`, such as `"<question>"`. Claude Code shows it as you type the command. The plugin README lists the same hint for Codex users.

A skill that drives your app to prove behavior is a verification skill. Use [verification-skill](../skills/verification-skill/SKILL.md) for it instead. [Verify and ship](06-verify-and-ship.md) covers it.

## Test a skill change before you trust it

A skill edit affects every future session. Test it like the experiment it is. The same goes for a skill you adopt from someone else.

```text
/swe:swe-mode update the review brief so reviewers flag missing migrations, and measure the change against the current version.
```

This matches the [evaluate-agent-change](../skills/swe-mode/playbooks/evaluate-agent-change.md) playbook. It is built around one failure mode. An agent that knows it is under test behaves differently. So each candidate gets an organic task in its own directory, with no evaluation words in any name or prompt, and never learns that other candidates exist. One judge on a different model scores every output under sanitized labels. The playbook grades chain-following from the files each candidate opened in its own transcript, not from what the candidate claims. It writes the metrics and pass thresholds before any run, and reports each metric with run count and interval.

Read every output yourself before you accept the verdict. If you disagree with the judge, suspect the rubric before your own judgment.

The repository also has offline skill-activation evals in [evals/skills/](../../../evals/skills/README.md). They check whether the right skill loads for a request, not whether the result is good. They call no model provider. No activation baseline exists yet. Before a broad release, validate the cases and run the harness tests:

```text
python3 evals/skills/skill_eval.py validate
python3 -m unittest discover -s evals/skills/tests
```

## Fork the plugin

swe is plain Markdown, scripts, and two JSON manifests. To change a playbook, a router rule, or a skill for your own use, fork the repository and install from your fork:

```text
/plugin marketplace add <you>/agent-toolbox
/plugin install swe@agent-toolbox
```

In Codex, run `codex plugin marketplace add <checkout>`, then `codex plugin add swe@agent-toolbox`. The Codex install is a copy, so add the plugin again after each source edit. To try a local edit in Claude Code, start `claude --plugin-dir <checkout>/plugins/swe`.

Follow the repository rules in [AGENTS.md](../../../AGENTS.md) and [contributing](../../../docs/contributing.md) when you change the fork:

- Keep the versions in `plugins/swe/.claude-plugin/plugin.json` and `plugins/swe/.codex-plugin/plugin.json` identical, and bump the patch number.
- Keep every skill reference pointed at a file that exists in the plugin.
- When you add or rename a playbook, add its line to the Playbooks list in the [router](../skills/swe-mode/SKILL.md#playbooks). The router matches only the playbooks it lists.
- Run the [release checks](../../../docs/release-checks.md) before a broad release.

Do not edit a skill in the middle of a task because it misbehaves. The router's rule is to fix a broken skill in its own PR and keep the task moving. A skill edit mixed into feature work is hard to review and impossible to evaluate.

Next: [Recipes and pitfalls](10-recipes-and-pitfalls.md).
