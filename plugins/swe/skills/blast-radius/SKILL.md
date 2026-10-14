---
name: blast-radius
description: "Find what a change could break beyond its diff, and prove the one fact it is safe because of by running real code. Use for 'blast radius', 'what could this break', or a risky diff before it ships."
---

# Blast radius

Find what a change breaks outside its diff before it ships. A caller list is
the easy part; a symbol search gives it in seconds. The job is the breakage
that a symbol search does not show.

This skill sits beside [how](../how/SKILL.md) and [why](../why/SKILL.md).
`how` tells you what the code does. `why` tells you why it has its shape.
Blast radius tells you what the change breaks somewhere else.

A risk write-up reads as convincing whether or not it is true. Do not hand
back a write-up alone. Find the one or two facts the change is safe because
of, and prove them by running real code.

## Evidence rungs

These rungs grade each safety fact only. Take the fact as far down the list as
is cheap, and report "stopped at rung `<name>`".

1. `asserted`: you stated it. Alone it proves nothing.
2. `cited`: you pointed at a real `file:line`, or at the library's own source.
3. `traced`: you walked the failure path step by step and showed it cannot
   reach.
4. `executed`: a script or test called the real code and would fail loudly if
   the fact were false.
5. `reproduced-live`: you showed it in the running application.

`executed` is usually one small script that imports the library version the
application ships and calls the exact function in question.

## Steps

1. `1-read-the-change`: Read the diff and the symbols it adds, changes, and
   deletes. State what the code now does differently, including what the
   diff does not spell out. Build the
   [code anchor](../why/SKILL.md#2-build-code-anchor) to get the commits and
   the PR.
2. `2-find-safety-fact`: Find the single fact the change is safe because of,
   such as "this call only drops cache entries that are already dead". Most
   changes that look risky are safe because of one fact. When it holds, most
   risky cases clear at once. Spend your time here, not on a long list of
   possible risks.
3. `3-look-past-grep`: Look where a symbol search stops. Read the source of
   each library the change calls, at its pinned version and with any local
   patch. Work out when things run: import-time side effects, microtasks,
   unmount and teardown, the framework's scheduling, and subprocess
   boundaries. Follow data that leaves the code: wire formats, JSON an API
   returns, database columns, another language that reads the same bytes,
   feature flags, and code three hops downstream.
4. `4-rate-each-risk`: Give each risk a real likelihood and a real cost. Keep
   confirmed risks apart from risks you checked and cleared. Follow the
   evidence rules of `why`. Cite a real `file:line`; a search that finds
   nothing is an answer too. Never invent a caller or an API.
5. `5-prove-the-fact`: Write a probe that runs the real code, run it, and
   paste the result. Put the probe in a scratch location such as
   `artifacts/temp/`. It becomes a permanent test only through the admission
   gate in [testing-code](../testing-code/SKILL.md).
6. `6-optional-independent-review`: For a large or wide change, give the
   change and your write-up to a reviewer with the
   [review brief](../../references/review-brief.md), and ask it to find a
   breakage you missed and to rerun your probe. Different models catch
   different real bugs. When more than one model is available, ask each the
   same question as a [swarm](../swarm/SKILL.md) race and merge the answers.

## Hand back

- **What it does**: what changed, including the part that is not obvious.
- **Safety fact**: the fact, the rung where it stopped, and the proof. Write
  "unproven" when no proof exists.
- **Risks**: for each, how it breaks, its `file:line`, its likelihood and
  cost, and how to check it. Paste the proof for the ones that matter.
- **Cleared**: what you checked and why it holds.
- **Before merge**: the cheapest test or reproduction that catches the real
  bug, including your probe.

Write the hand-back through [unslop](../unslop/SKILL.md) and cite real code.
This write-up feeds the Blast Radius section of the
[PR body](../ship-pr/references/pr-body.md). Before any part of it goes into a
branch, commit, or PR body, apply the privacy rule in
[ship-pr](../ship-pr/SKILL.md).
