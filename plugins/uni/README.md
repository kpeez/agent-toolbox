# Uni

Uni bundles eight conversational tutoring skills and a teaching workspace
skill. It helps the learner
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

Uni `0.1.2` installs all nine skills through the native plugin manager. Shared
references stay inside the plugin; no separate installer or runtime is needed.
If you previously copied the chat skills into a project, preserve any edits
before removing those copies to avoid duplicate discovery.

`teach` was previously a standalone skill. After updating Uni, remove only a
legacy `~/.codex/skills/teach` or `~/.agents/skills/teach` symlink that points to
the former repository path. Preserve independently edited directories. Its
workflow, templates, upstream license, and explicit-only invocation are intact.

## Invoke the tutor

In Codex, mention the skill with `$`; use the selector if needed. These prompts
work with the installed plugin:

```text
$learn Help me discover why gradient descent is useful. I know derivatives and have 25 minutes.
$learn-feynman Test my understanding of Bayesian updating. Ask me to explain first.
$learn-review Drill the concepts from our last lesson for ten minutes, one question at a time.
$uni:teach Build a learning workspace with short HTML lessons about linear algebra.
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
| `teach` | Author a persistent learning workspace with HTML lessons and reusable references; invoke explicitly |

Start with the umbrella skill unless a particular exercise is already clear.
Lessons mix explanation with purposeful questions and exercises: predict an
outcome, explain a mechanism from memory, complete a missing step, test an
argument, or apply an idea in a fresh setting. There is no required stage
sequence. The tutor uses your actual answer to choose useful feedback and the
next exercise.

At the end, a brief synthesis or optional chat handoff summary can help you
continue later. `learn-review` revisits concepts you choose or material already
encountered in the chat. Anki handles long-term review outside Uni.

Use `teach` when you want lesson files and a persistent learning workspace.
It maintains a mission, learning records, source list, glossary, and reusable
lesson assets. Invoke it explicitly with `$uni:teach` in Codex or `/uni:teach`
in Claude Code. Its workspace-authoring workflow is separate from the chat
tutor's one-question-at-a-time interaction.

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

Release checks verify paired manifests, catalogs, and bundled references. The
[held-out evaluation guide](evaluations/README.md) distinguishes next-turn
behavior checks, simulated examples, actual host activation, and educational
efficacy. Check the retained evaluation
results and [build report](BUILD-REPORT.md) for tests actually executed and
remaining limits. Generated run traces and scores stay in the repository's
ignored `artifacts/uni-build/` directory; they are not distributed with the plugin.

## Files

- `skills/*/SKILL.md`: nine operational entry points and UI metadata.
- `skills/learn/references/`: shared contract, examples, and evidence notes.
- `skills/teach/`: workspace-authoring workflow, four format templates, and
  upstream license.
- `evaluations/`: behavioral scenarios, rubrics, and historical review.
- `NOTICE`: original-material license and source attribution.
