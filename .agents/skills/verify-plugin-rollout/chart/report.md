# PluginRollout

TLC reached 60 states and 288 steps. The chart draws 7 states and 7 arrows.
The chart does not draw 108 steps that stay in one chart state.
The view hides 120 steps, so the chart does not draw them.

## DocStepsReachEveryFolder breaks
The shortest path has 5 steps:
0. No PR open
1. a PR edits a plugin: PR open
2. the checks pass: Checks pass
3. the PR merges: Merged, no folder updated
4. you run the README update steps: Merged, some folders updated
5. you install the merged SHA in the Hermes profile: README steps done, another Claude Code folder stale

## Rules that hold
NeverLoadsUncommittedEdits, FoldersListed, EntriesPointAtFolders, NoCrossPluginNames
