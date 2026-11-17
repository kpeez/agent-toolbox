---
name: research-skill
description: "Create or maintain a research project's own skills: its research-context skill, and one skill per recurring procedure such as a statistics pipeline or an eval protocol. Use when a procedure repeats, when the user corrects one, or when asked to codify, check, or update one."
argument-hint: "[procedure, or context]"
---

# /research-skill

Target: $ARGUMENTS

A project skill holds one procedure of this project: its real commands, the domain's validity checks, one known-good run, and the gotchas found so far. The next agent reads it cold, mid-task, with no memory of this session. Write it for that agent. Lay the skill out as [project skill layout](../../references/project-skill-layout.md) says.

## Choose the mode

Look in `.agents/skills/` and `.claude/skills/`, in each directory from the working directory up to the repository root. Then pick one mode and say which.

- Context mode: no `research-context` skill exists, or the user asks for one.
- Create mode: the user named a procedure, or this session repeated one, and no skill covers it.
- Maintain mode: a skill covers the procedure, or the pipeline, the data, or the conventions changed.

When the target is unclear and several skills could fit, ask which one, and name the candidates.

## Context mode

1. `1-survey-the-repo`: Answer from files, scripts, docs, and shell history. Ask the user only what you cannot observe. Find these:
   - where the data lives, and its format;
   - the units and the sample structure (subjects, sessions, runs, partitions);
   - the variables;
   - how the data arose (acquisition, preprocessing);
   - known confounds;
   - analysis conventions (thresholds, corrections, splits, seeds);
   - where results go;
   - the commands that run the pipeline.

   Done when each item has an answer or a named gap.

2. `2-write-research-context`: Write `.agents/skills/research-context/SKILL.md`. Give it these sections: Data, Variables, How the data arose, Known confounds, Conventions, Commands, Procedure skills (a list, empty at first; each entry marked live or proposed), Open questions. The description says when to load it: "Use before any analysis, experiment, or claim about <project>". Each convention names its source: a paper, a doc, or "project convention". Put gaps in Open questions. Never fill a gap with a guess.

   Done when every section exists and no sentence is a placeholder.

3. `3-prove-it`: Pick three concrete questions about the data, such as the number of subjects, the unit of one row, or the split rule. Answer each from the skill alone. Then check each answer against the files. Fix what is wrong.

   Done when all three answers match the files.

4. `4-hand-over`: Confirm that Git tracks every file of `.agents/skills/research-context/` and tracks no link under `.claude/skills`. Confirm that `.claude/skills/research-context/SKILL.md` resolves through the link. Report the path and the three proof answers.

   Done when the report states each of these, or names the one that is unverified.

## Create mode

1. `1-pin-the-procedure`: Name its inputs, its outputs, and the decisions inside it. Take the real commands from this session or from shell history, not from memory.

   Done when you can list each command with its inputs and outputs.

2. `2-run-it-as-it-is`: Run the procedure on the checkout as it stands. For a long pipeline, use the smallest real input that goes through every stage, such as one subject or one partition. Fix a break, or report it exactly and stop. A skill written against a broken pipeline teaches wrong steps.

   Done when the procedure runs to its output.

3. `3-collect-validity-checks`: Take checks from three sources: the `research-context` confounds and conventions; the domain's published conventions, with a citation for each; and each correction the user made. Make a check runnable when you can, such as a script assertion. Otherwise write it as a precise question. Never invent a check that the domain does not support.

   Done when each check has a source and a form (assertion or question).

4. `4-build-the-known-good-run`: Choose one of three forms. The first is a small real input with its recorded expected output. The second is simulated data with a planted, known answer that the procedure must recover; see [simulate-before-you-trust](../principle-simulate-before-you-trust/SKILL.md). The third, and strongest, is a null input that must show no effect. Keep the input small enough to commit. Store it in the skill folder.

   Done when one command runs the procedure on this input and compares the result with the expected answer.

5. `5-write-the-skill`: Write `.agents/skills/<procedure>/SKILL.md` and its `scripts/`. Give `SKILL.md` these sections: When to use, Inputs, Procedure (exact commands), Validity checks, Known-good run, Provenance (what to record on every run), Gotchas. The description names the procedure and says when to use it. Leave no placeholder.

   Done when every command in the skill is one you ran.

6. `6-prove-the-skill`: Follow the skill's own text, end to end, on real data. Include the known-good run. Fix what fails. A skill that never ran is a draft, not a deliverable.

   Done when one full run followed the text with no unwritten step.

7. `7-hand-over`: Add the skill to the Procedure skills list in `research-context` marked live, or change its proposed entry to live. Confirm that Git tracks every file of the folder and tracks no link under `.claude/skills`, neither the folder link nor a per-skill link. Confirm that `.claude/skills/<procedure>/SKILL.md` resolves through the link. Report the skill path, the checks, and the known-good result.

   Done when the report states each of these, or names the one that is unverified.

## Maintain mode

Maintain only skills in the "Procedure skills" list of `research-context`, and leave every other skill under `.agents/skills/` alone.

1. `1-rerun-the-known-good-run`: Rerun the known-good run. A failure is a finding.
2. `2-compare-with-the-pipeline`: Compare the skill's commands, paths, and conventions with the pipeline as it is now.
3. `3-fold-in-corrections`: Fold each new user correction into the skill as a check or a gotcha, in the user's terms.
4. `4-report-the-outcome`: End with one outcome for each skill, and say which: unchanged, updated, or retired. Delete a retired skill's folder and remove it from the "Procedure skills" list in `research-context`.

Edit only project skill folders. When the pipeline's output looks wrong, report it. Do not hide it with a skill edit.

## Rules

- One procedure per skill.
- Write the text for an agent that arrives cold.
- Record what the user corrected, in the user's terms.
- Keep project data out of the skill, except the small known-good input.
