# lab

lab adds research and experiment skills: cited memos and reports, bounded
experiment loops, and plot guidance.

## Install

Each plugin installs alone. Pick one way, then start a new session.

Claude Code plugin:

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install lab@agent-toolbox
```

Codex CLI plugin:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add lab@agent-toolbox
```

Antigravity CLI (`agy`):

```text
agy plugin install https://github.com/kpeez/agent-toolbox/tree/main/plugins/lab
```

Skills only, with [`npx skills`](https://github.com/vercel-labs/skills), for
Claude Code, Codex, and other agents that read Agent Skills:

```text
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/lab
```

This installs the lab skills and no other plugin. Install all of them, because
they read each other by path. Add `-g` to install for your user instead of
the current project.

To update:

- Claude Code: `claude plugin marketplace update agent-toolbox`, then
  `claude plugin update lab@agent-toolbox`.
- Codex: `codex plugin marketplace upgrade agent-toolbox`, then
  `codex plugin add lab@agent-toolbox` again.
- agy: run the `agy plugin install` command again. It replaces the old copy.
- npx skills: `npx skills update`.

## Go deeper, then route each research task

The Claude Code plugin adds a SessionStart hook with two rules:

- Run [`go-deeper`](./skills/go-deeper/SKILL.md) on each new task: expert
  moves, raw sources, real methods, and an outside check, then the rewritten
  task. swe, lab, and uni each carry an identical copy, so each plugin works
  alone.
- Load [`lab-mode`](./skills/lab-mode/SKILL.md) on each research task: reading
  or judging sources, an experiment or eval, or a project's own research
  skills. It routes the task to a playbook and tracks each step. A plain
  figure request goes straight to `making-plots`.

agy runs no hooks, but it loads the same rules from
[`rules/AGENTS.md`](./rules/AGENTS.md). Codex plugins and the skills-only
install have no hooks. Copy the line in
[`hooks/session-start.md`](./hooks/session-start.md) into `AGENTS.md` or
`CLAUDE.md` to get the same behavior.

## Project skills: the flywheel

Lab is built around each project's own skills.
[`research-skill`](./skills/research-skill/SKILL.md) writes and maintains them
in the project's `.agents/skills/` folder, as the
[project skill layout](./references/project-skill-layout.md) says:

- `research-context`: one per project. It holds the data, the variables, how
  the data arose, the known confounds, and the analysis conventions. Every
  lab playbook loads it when it exists.
- One skill per recurring procedure, such as `fmri-glm-stats` or
  `retrieval-eval`. Each skill holds the real commands, the domain's
  validity checks, one known-good run, and the gotchas found so far. A skill
  counts only after it has run once on real data.

Every research playbook ends with a step that asks two questions. Did this
run repeat a procedure? Did the user correct one? A yes proposes or updates a
project skill, so the next run on the project starts from it.

## Playbooks and principles

`lab-mode` picks one playbook per task and copies its steps into the task
list:

| Playbook | Use for |
| --- | --- |
| [`bootstrap-project`](./skills/lab-mode/playbooks/bootstrap-project.md) | Set up a research repository's `research-context` and first procedure skill |
| [`codify-procedure`](./skills/lab-mode/playbooks/codify-procedure.md) | Turn a procedure into a proven project skill |
| [`maintain-project-skills`](./skills/lab-mode/playbooks/maintain-project-skills.md) | Recheck project skills after the pipeline or data changed |
| [`appraise-source`](./skills/lab-mode/playbooks/appraise-source.md) | One paper, preprint, blog post, or result to judge |
| [`review-literature`](./skills/lab-mode/playbooks/review-literature.md) | What a body of work shows on a question |
| [`analyze-results`](./skills/lab-mode/playbooks/analyze-results.md) | Results or logs that need a conclusion |
| [`run-experiment`](./skills/lab-mode/playbooks/run-experiment.md) | One designed comparison, ablation, or eval run |

Each playbook step names what it applies: a principle, the
[claim checklist](./skills/lab-mode/references/claim-checklist.md), a lab
skill, or a project skill. A principle is a short skill named
`principle-<slug>`, hidden from the model's skill list, so it costs no context
until a step reads it. There are four:

- `encode-the-procedure`: the second time you do a procedure, or after a
  correction, make or update a project skill.
- `simulate-before-you-trust`: run data with a known answer through the
  pipeline before you trust it on real data.
- `write-the-decision-first`: write the hypothesis, the metric, and the
  decision rule before the run.
- `grade-the-evidence`: give each claim a grade: `strong`, `moderate`,
  `weak`, or `unsupported`.

Use a principle's name to steer a run in one phrase:

```text
simulate before you trust. run the GLM on null data 200 times and show me the false-positive rate.
```

## Figure reminder

The Claude Code plugin also adds a PostToolUse hook,
[`hooks/figure-reminder.py`](./hooks/figure-reminder.py). When a shell command,
an edit, or a write touches plotting code, figures, or a PNG, it tells the
agent to load `making-plots`. It fires at most once per session, and never after
the skill has loaded. It needs `python3` on `PATH`.

## Skills

Each command shows its arguments: `<x>` is required and `[x]` is optional.
Claude Code shows the same hint when you type the command. In Codex, type `$`
in place of `/`.

| Command | Use for |
| --- | --- |
| [`/lab:go-deeper <task>`](./skills/go-deeper/SKILL.md) | A task made deeper, not bigger: expert moves, raw sources, real methods, and an outside check. Runs on its own at the start of a new task |
| [`/lab:lab-mode <task>`](./skills/lab-mode/SKILL.md) | Route a research task to its playbook and track each step. The session-start hook loads it for research tasks |
| [`/lab:research-skill [procedure, or context]`](./skills/research-skill/SKILL.md) | Create or maintain a project's own research skills: its `research-context` and one skill per recurring procedure |
| [`/lab:research <question>`](./skills/research/SKILL.md) | One cited memo for a bounded question or a source audit |
| [`/lab:deep-research <topic>`](./skills/deep-research/SKILL.md) | A multi-lane research program with briefs, lane evidence, and an audited report |
| [`/lab:autoresearch <metric goal>, or cleanup <run tag>`](./skills/autoresearch/SKILL.md) | A bounded experiment loop against an approved metric and evaluator, and its cleanup |
| [`/lab:making-plots <results or figure>`](./skills/making-plots/SKILL.md) | Make, rerun, restyle, or review result figures and results tables, and their plotting code |
| [`/lab:visualizing-data <plot or plotting code>`](./skills/visualizing-data/SKILL.md) | Review plots for honest scales and accessibility |

## Autoresearch files

A new run keeps its program, ledgers, logs, configuration, and figures under
`artifacts/autoresearch/<tag>/` in the repository. A configured vault gets the
closeout notes and only the figures those notes embed.
