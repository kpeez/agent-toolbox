---
name: verify-tech-tree
description: Explore every order of learner events (lesson, review, placement, a day passing) on the real uni tech-tree script and check its gate and scheduling rules in every state. Use when a change touches plugins/uni/skills/tech-tree/scripts/tech_tree.py (cmd_record, cmd_place, cmd_next, frontier, unmet_ancestors, credit) or the rules in its SKILL.md or GRAPH-FORMAT.md, or when the check fails.
---

# Verify the tech-tree gate

## The rules

Each rule holds in every state that the events can reach:

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `LessonGate` | `record` accepts a lesson only when every ancestor is met. | A learner starts a topic without its prerequisites. |
| `NextIsLegal` | `next` names a lesson or retry only for an unmet topic with every ancestor met, and a review only for a met topic. | The tutor is told to teach a topic that `record` then refuses. |
| `MetHasDue` | A met topic (mastered or conditional) has a review date. | A met topic is never reviewed again. |
| `UnmetHasNoDue` | An unmet topic has no review date. | `next` schedules a review of a topic the learner never passed. |
| `ConditionalNeedsMetAncestors` | A conditional (placed) topic has every ancestor met. | Placement credit stands on a prerequisite the learner has shown they do not know. |

## Run it

From the repository root:

```sh
python3 .agents/skills/verify-tech-tree/scripts/check.py
```

It needs Python 3 and nothing else. It takes about one minute. It exits 0 only
when each rule's result matches `EXPECTED` in `scripts/check.py`, and each
mutant breaks the rule it targets, so each rule is shown able to fail. For a
rule that breaks, it prints the shortest event path.

`--no-mutants` skips the mutants.

## How it works

This is not a hand model. `scripts/check.py` loads
`plugins/uni/skills/tech-tree/scripts/tech_tree.py` and calls its real
`cmd_record`, `cmd_place`, and `cmd_next`. A breadth-first search applies every
event to every reached state:

- `record <topic> pass`, `record <topic> pass --helped`, `record <topic> fail`;
- `place <topic> pass`, `place <topic> fail`;
- a day passes: each review date moves one day closer, and today's failures
  are forgotten.

The course is `course.json`: a chain `base`, `middle`, `top`, with key
prerequisites two edges back and both `encompasses` weights.

Bounds, at the top of `scripts/check.py`: at most 7 events, at most 2 fails
and 3 repetitions per topic, and review dates at most 2 days overdue. The
check covers every order of events inside these bounds, about 76,000 states.
It does not cover a longer history, a wider graph, or `validate`.

The check computes "met" and "unmet ancestors" itself, not with the script's
functions, so a mutant of those functions cannot hide a break.

Coverage: `cmd_record`, `cmd_place`, `cmd_next`, `frontier`,
`unmet_ancestors`, `due_reviews`, `credit` in `tech_tree.py`.

Sync commit: the commit that adds this skill. At that commit the check
describes the code.

## When a change touches the covered code

1. Run the check before and after the change.
2. A rule that breaks after the change: read the printed path, and replay it
   with the real CLI in a scratch folder (`tech_tree.py record ... --graph
   course.json --progress <scratch>/progress.json --date 2026-01-01`). Every
   step runs, so it is a bug in the change, or the rule changed on purpose.
3. When the rule changed on purpose, update the rule in the table above, its
   sentence in the tech-tree `SKILL.md` or `GRAPH-FORMAT.md`, and `EXPECTED`,
   in the same change. Cite the reason. Never flip `EXPECTED` only to make the
   check pass.
4. A new event or status in the script: add it to `events()` or `met()`
   first, then rerun.
5. After you confirm the check describes the code, set the sync commit above
   to the commit you checked.
