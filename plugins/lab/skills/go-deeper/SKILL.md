---
name: go-deeper
description: "Make a new task deeper, not bigger, before you start: what a top expert would do, the rawest source, the real methods and tools, and a check outside you and the user. Use first on any new task, request, or proposal. Skip chat, quick facts, and fully specified mechanical edits."
argument-hint: "<task>"
---

# Go deeper

Task: $ARGUMENTS

When the task line is empty or still holds an unreplaced placeholder, the
task is the user's current request.

## Skip

Skip this skill for chat, a quick factual answer, a mechanical or fully
specified edit, a follow-up inside a task you already framed, and "just do
it". Run it once per task.

## Answer four questions

1. **Expert moves.** What would a top professional in this field do here that
   the user did not ask for?
2. **Raw material.** What is the rawest material they would start from,
   instead of a summary, a digest, or your memory? For example: the primary
   source, the real data, the logs, the code, the upstream original.
3. **Methods and tools.** Which specific methods and tools would they use?
   Name them.
4. **Outside check.** What, other than you or the user, would show that the
   result is right? For example: a test, a benchmark, a primary source, a
   reproduction, or behavior that a user can observe.

Find facts yourself before you answer: read the code, the docs, and the
sources, or run a command. An answer that rests on a guess is not an answer.

## Deeper, not bigger

Keep an addition only when it changes the source, the method, or the check.
Reject an addition that only adds scope, deliverables, or length. Loosen a
constraint that does not serve the goal as readily as you add one that does.
Always keep one outside check.

## Constraints only the user can set

When an answer depends on a product or preference constraint that no
observation can settle, ask the user about those constraints only. Use the
`interview-user` skill when it is installed. Otherwise ask one round, each
question with your recommended answer. Do not ask for a fact you can look up.

## Output

Before the work, give a frame of five lines or fewer: one line for each
question, then the rewritten task in one or two sentences. Then do the
rewritten task. Do not wait for approval unless an open constraint blocks the
work. The frame does not replace the work.

When the user asks only for a better prompt, give the four answers and the
rewritten prompt, then stop.
