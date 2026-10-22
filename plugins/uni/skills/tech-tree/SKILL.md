---
name: tech-tree
description: Build a course as a prerequisite graph (tech tree) before any lesson, then gate each topic on mastered prerequisites, place the learner, remediate failures, and schedule reviews. Use when a course, curriculum, or multi-session lesson series starts, or when a course folder has a tech-tree.json.
argument-hint: "<course topic or course folder>"
---

# Tech tree

A course is a graph of small topics. A learner starts a topic only when every topic below it in the graph is met: mastered, or placed by the diagnostic. Mastery comes only from correct answers given without help. This follows Math Academy's design; [the design notes](references/design-notes.md) give the sources and limits.

The course folder holds two files. [GRAPH-FORMAT.md](GRAPH-FORMAT.md) defines both:

- `tech-tree.json`: the topics and prerequisite edges. Write it first.
- `progress.json`: the learner's state. Only the script writes it.

Run the script for every gate, placement, and result. Do not track state by hand:

```text
python3 -I <this skill>/scripts/tech_tree.py --graph <course>/tech-tree.json <command>
```

Commands: `validate`, `mermaid`, `frontier`, `next`, `record <id> pass|fail [--helped]`, `place <id> pass|fail`, `status`. The options `--graph`, `--progress`, and `--date YYYY-MM-DD` (today) go before or after the command.

## 1. Build the graph before any lesson

1. Read the learner's goal and the best sources. In a `teach` workspace, read `MISSION.md` and `RESOURCES.md`.
2. Write topics. Each topic has one goal ("Learner can ..."), one check (the kind of items that show the goal), 10-30 minutes of work, and 1-4 knowledge points (KPs) of rising difficulty.
3. Write prerequisite edges. For each candidate edge A to B, ask: "Can a learner pass B's check without A's skill?" If yes, drop the edge. If no, store the reason in `requires`.
4. Tag each KP with its key prerequisites: the earlier topics the step uses directly. They can be several edges back.
5. Optional: add `encompasses` weights (0.5 or 1.0) only where B's problems practice A's skill. A prerequisite is not always encompassed.
6. Run `validate`. Fix every error. Split topics that get size warnings.
7. Ask a fresh reviewer subagent to audit the edges with [the edge review brief](references/edge-review.md). Fix what it finds. If no subagent is available, run the brief yourself in a second pass and say so.
8. Show the learner the `mermaid` output. Start lessons only after the learner accepts the tree.

When a lesson shows a missing or wrong edge, change the graph and run `validate` again. Keep topic ids stable, because `progress.json` uses them.

## 2. Place the learner

Do not accept self-ratings. Learners overestimate what they know.

1. Ask one checked question on a topic in the middle of the graph. Choose the simplest question that uses the topic and its prerequisites.
2. Run `place <id> pass` or `place <id> fail`. A pass gives conditional credit to the topic and its ancestors. A fail removes conditional credit from the topic and its descendants.
3. Move down after a fail and up after a pass. Stop when the frontier is stable or after about 20 questions.

A conditional topic counts as met. It gets a review 3 days later. A failed review or placement removes its credit and the credit of its conditional descendants.

## 3. Teach only from the frontier

1. Run `next`. It names a lesson, a retry, or a review. Do not teach a locked topic. `record` refuses it. A failed lesson is not offered again on the same day.
2. A lesson is a short introduction, then for each KP one worked example and 2-5 practice questions. Teach new topics explicitly. Keep discovery methods for reviews and transfer.
3. Write the practice items before the lesson, from the topic's check. They must differ from the worked example. Do not soften them during the lesson. Use fresh items on a retry.
4. Pass rule: in each KP, 2 consecutive correct answers without help, within 5 questions. Order matters: wrong, right, right shows learning; right, wrong, right does not. The lesson passes when every KP passes.
5. Run `record <id> pass` or `record <id> fail`. If the learner had a hint, an example during the attempt, or the answer, add `--helped`. A helped pass never masters a topic.

Use [learn-worked-example](../learn-worked-example/SKILL.md) for the KP pattern and [the tutoring contract](../learn/references/tutoring-contract.md) for questions and grading. The learner's controls still work. After "hint", "show an example", or "just explain", the next answer is helped. After "skip", record nothing.

## 4. Remediate with the ladder

The script prints the next rung after each failed `record`:

1. A KP goes badly: add questions, up to 5.
2. The lesson fails: stop it. Teach another frontier topic. Retry later with new questions.
3. The retry fails: review the topic's key prerequisites, one `record` each.
4. A key prerequisite fails its review: the script sends it back to `learning`. Reteach it. Every topic above it stays locked until then, and its ladder starts again.
5. The prerequisites pass and the topic fails again: the topic is too big or an edge is missing. Split the topic or add the edge.

Do not re-explain the same way again and again. Do not lower the check.

## 5. Review

- A mastered topic gets review dates at 1, 3, 7, 14, 30, and 60 days. A review is one or two fresh items, mixed with other topics, without notes or examples in view.
- `next` puts at least one lesson after every three reviews. It prefers a lesson that fully encompasses a due review of a mastered topic, because that lesson practices the old topic too.
- An unhelped pass gives credit to the mastered topics it encompasses: 1.0 or 0.5 repetitions, which moves their due dates later. Credit counts only within half an interval of the due date; earlier practice is too soon to count. It flows on through further 1.0 edges.
- A failed review brings the review back the next day and pulls the due dates of topics that encompass it earlier. A second failed review in a row sends the topic back to `learning`.

Close each session with `status` or `mermaid`, so the learner sees the progress.

## Limits

This is a coarse version of Math Academy's system. It has no per-learner speed model, no population statistics, and no fine fractional weights. An LLM-drafted graph has wrong edges; the review step and the ladder's step 5 catch some of them. No study tests this combined design.
