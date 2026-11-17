# maintain-project-skills

Applies when: a request to check the project's procedure skills after the pipeline, the data, or the conventions changed.

You own the truth of every project skill. A skill that no longer runs is worse than none.

A passing known-good run shows only that the skill still works on its own check. Compare the skill with the pipeline as well. Give each skill exactly one outcome.

1-list-project-skills: When no `research-context` skill exists, route to `bootstrap-project` and stop. Otherwise, list each entry of the "Procedure skills" list in `research-context`, and give each its last recorded known-good result. Leave every other skill under `.agents/skills/` alone. (bootstrap-project, research-context)
2-rerun-known-good-runs: Run the known-good run of each live skill on the list. Record pass or fail with the output. (simulate-before-you-trust)
3-compare-with-the-pipeline: For each skill, list the commands, paths, data versions, and conventions that changed since the skill was written. Name the commit or file that shows each change. (research-context)
4-fix-or-retire: Give each skill one outcome: unchanged, updated, or retired. Rerun the known-good run of each updated skill until it passes. Delete each retired skill's folder. (research-skill)
5-refresh-the-context: Make `research-context` match the pipeline now. In its "Procedure skills" list, mark each entry live or proposed, and remove each retired skill. (research-skill)

Reply: a table of skill, known-good result, outcome, and change.
