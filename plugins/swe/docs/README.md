# The swe guide

swe works best when you stop micromanaging the agent. You say what you want
and how you will know it is done. `/swe:swe-mode` picks the playbook, runs the
other skills as the steps need them, and shows you the evidence. This guide
teaches that habit with realistic prompts.

The pages cover these topics:

1. [Set up swe](01-setup.md). Install the plugin and run a first task.
2. [Route work through `/swe:swe-mode`](02-route-work.md). Give it a goal and see it pick a playbook.
3. [Understand the code](03-understand.md). A read-only investigation, then `how`, `why`, and `recall` before you edit anything.
4. [Design the change](04-design.md). `architect`, `interview-user`, prototypes, reviewers, and plans before code sets a shape.
5. [Build and clean the change](05-build-and-clean.md). The build playbooks, test-first work, `no-comments`, and `writing`.
6. [Verify and ship](06-verify-and-ship.md). Prove behavior on the real app, vet numbers, then open a focused PR and drive it to merged.
7. [Run long work](07-long-runs.md). Autonomous runs, decision logs, handoffs, delegation, and where swe keeps its files.
8. [Steer with principle names](08-principles.md). The 25 names that redirect an agent during a task.
9. [Make it yours](09-make-it-yours.md). `correct` for repeated mistakes, skill edits, and how to test a skill change.
10. [Recipes and pitfalls](10-recipes-and-pitfalls.md). Prompts to copy and mistakes to skip.

Read the pages in order the first time. After that, each page stands alone.

## If you only remember one thing

Give the agent a goal and a way to check it, in your own words:

```text
/swe:swe-mode the export writes duplicate rows when a retry lands mid-run. repro first, then fix and verify.
```

You do not need to name a playbook or list skills. "repro first" and a
checkable outcome are all the signal the router needs. It matches the
`fix-bug` playbook, copies the steps into the task list, and loads the right
skills as each step starts.

Next: [Set up swe](01-setup.md).
