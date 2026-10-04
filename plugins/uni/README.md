# Uni

Uni is a coherent tutor with eight reusable skills. It helps the learner
reconstruct an idea, criticize an argument, explain a mechanism, practice
retrieval and transfer through questions, active recall, and concept exercises.
These are part of normal lessons. The tutor asks one main
question at a time and waits for the learner's actual response.

Use ordinary controls such as “hint,” “smaller step,” “show an example,” “just
explain,” “quiz me,” “harder,” “skip,” and “stop.” Instruction follows when
prerequisites are missing or progress stalls. The learning loop is a repertoire,
not a required sequence. Ordinary coding requests do not enter tutoring mode.

## Install from the marketplace

For Codex:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add uni@agent-toolbox
```

For Claude Code:

```text
claude plugin marketplace add kpeez/agent-toolbox
claude plugin install uni@agent-toolbox --scope user
```

If the marketplace is already configured, refresh it before installing with
`codex plugin marketplace upgrade agent-toolbox` or
`claude plugin marketplace update agent-toolbox`. Start a fresh session after
installation. Codex invocation uses `$learn`; Claude Code uses `/uni:learn`.

## Optional project-local skill copy

Install all eight sibling directories together. Their shared references use
relative paths to the shared material in `learn/`. Copying one skill alone produces
an incomplete installation.

The supported Codex layout is `<project>/.agents/skills/<name>/SKILL.md`.
Codex also supports symlinked skill folders; plugins are preferred for bundle
distribution. See the [official skills documentation](https://learn.chatgpt.com/docs/build-skills).
The manifests and local catalogs package this checkout as `uni` version `0.1.1`.

From the `agent-toolbox` checkout, use Nushell to copy the whole skill set into
an existing project:

```nu
nu plugins/uni/scripts/install.nu /absolute/path/to/your-project
```

The installer requires an explicit project path. It refuses existing Uni skill
names, including symlinks, before copying. It preserves other skills. It requires
Nushell only for installation; the installed tutor does not depend on Nushell.
Start Codex in that project. If the skills do not appear, restart Codex. Avoid
installing both a direct skill copy and the plugin in the same scope: duplicate
names can appear separately in the selector.

Plugin-capable hosts can use the complete `plugins/uni` bundle through their
local-plugin workflow. Publication and actual host activation are separate from
the checked-in packaging and clean-copy verification. The existing standalone
[`teach`](../../skills/teach/SKILL.md) remains a separate skill.

## Invoke the tutor

In Codex, mention the skill with `$`; use the selector if needed. These prompts
work with the documented complete local copy:

```text
$learn Help me discover why gradient descent is useful. I know derivatives and have 25 minutes.
$learn-feynman Test my understanding of Bayesian updating. Ask me to explain first.
$learn-review Drill the concepts from our last lesson for ten minutes, one question at a time.
```

| Skill | Use |
| --- | --- |
| `learn` | Establish a small goal, check relevant knowledge, route and resume |
| `learn-genetic` | Reconstruct the problem that makes an idea useful |
| `learn-refute` | Test a conjecture or argument and repair the failing part |
| `learn-feynman` | Diagnose and revise the learner's own explanation |
| `learn-worked-example` | Study a small example, complete missing steps, then work independently |
| `learn-quiz` | Ask and grade one source-grounded retrieval question at a time |
| `learn-review` | Revisit selected or recent concepts through chat drills |
| `learn-transfer` | Select and apply a method in a new situation |

Start with the umbrella skill unless a particular exercise is already clear.
Lessons mix explanation with purposeful questions and exercises: predict an
outcome, explain a mechanism from memory, complete a missing step, test an
argument, or apply an idea in a fresh setting. There is no required stage
sequence. The tutor uses your actual answer to choose useful feedback and the
next exercise.

At the end, a brief synthesis or optional chat handoff summary can help you
continue later. `learn-review` revisits concepts you choose or material already
encountered in the chat. Anki handles long-term review outside Uni.

## Conversation scope

Uni teaches within the chosen chat host. Questions stop at a real turn boundary;
the tutor waits for your response and gives explanation or help when needed.
It does not simulate your answers. Success after hints or explanation is
distinguished from an independent attempt.

The suite has no learner database, custom scheduler, retention target, or Anki
integration. Prompts and responses are handled by the chosen host. No separate
runtime or learning account is needed for the lessons.

## Evidence and verification

Read the [evidence matrix](skills/learn/references/evidence-matrix.md),
[research notes](skills/learn/references/research-notes.md), and
[source registry](skills/learn/references/source-registry.json) for the design's
support and limits. Registry entries distinguish full text, excerpts, abstracts,
and bibliographic access as of 2026-10-03. The bundle contains original notes
and links, not redistributed copyrighted books or papers.

Historical methods motivate exercises. Experimental studies and syntheses
support individual learning choices in specific settings. Practitioner advice
helps formulate focused questions. Scheduling and import sources remain as
clearly marked unused background from the earlier design. None validates this
exact combined AI tutor.
Exposure, helped performance, independent performance, delayed recall, and
transfer remain separate evidence. The two-stalled-attempt escalation default
is an engineering choice.

Packaging checks verify the bundle and installer. The
[held-out evaluation guide](evaluations/README.md) distinguishes next-turn
behavior checks, simulated examples, actual host activation, and educational
efficacy. Check the retained evaluation
results and [build report](BUILD-REPORT.md) for tests actually executed and
remaining limits. Generated run traces and scores stay in the repository's
ignored `artifacts/uni-build/` directory; they are not distributed with the plugin.

## Files

- `skills/*/SKILL.md`: eight operational entry points and UI metadata.
- `skills/learn/references/`: shared contract, examples, and evidence notes.
- `tests/` and `evaluations/`: packaging and behavioral verification.
- `scripts/install.nu`: explicit-target, non-overwriting local installer.
- `NOTICE`: original-material license and source attribution.
