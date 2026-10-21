---
name: verification-skill
description: "Create or maintain this project's verification skill: a reusable way to launch, drive, and observe the real app, plus a feature map. Use when the user asks for a verification skill or to audit one."
argument-hint: "[app or surface]"
---

# /verification-skill

A verification skill is a project-local skill that launches the real app, drives a feature the way a user does, and captures evidence. Its evidence supports a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict, as [principle-prove-it-works](../principle-prove-it-works/SKILL.md) defines. The next agent reads it cold, mid-task, with no knowledge of the app. Write it for that agent.

## Choose the mode

Find the project's existing verification skill by observation: a project-local skill whose body has launch and drive sections and a feature map, usually `verify-<app>`. Look in `.claude/skills/` and `.agents/skills/`, in each directory from the working directory up to the repository root. When the user named an app or surface, consider only skills that cover it.

- None found: use create mode.
- One found: use maintain mode.
- Several found: ask which one, and name the candidates.

Say which mode you chose.

## Create mode

1. `1-interview-the-repo`: Answer from the codebase. Ask the user only what you cannot observe.
   - Surface: what the user touches (web UI, CLI or TUI, desktop app, API, mobile app, library). Pick the primary surface and note the others.
   - Run: how the app starts locally. Use the repo's own dev command (package scripts, Makefile, README quickstart). Note ports, env vars, seed data, and auth.
   - Drive: how an agent interacts with it. Use existing harnesses first (Playwright or Cypress specs, expect scripts, PTY helpers, curl-able endpoints, a debug port). Then pick a generic recipe: browser or CDP for web and Electron, a tmux or PTY harness for CLI and TUI, plain HTTP for services.
   - Observe: what evidence you can capture (screenshots, terminal transcripts, response bodies, logs, exit codes, database state).
   - Isolate: whether two instances can run side by side (ports, data dirs, profiles). If not, the generated skill says so and refuses to double-drive a shared instance. A refusal costs less than a corrupted user session.

   Done when each of the five has an answer or a named gap.

2. `2-fix-the-checkout`: Build and start the app as it is. A skill written against a broken base teaches wrong steps. Fix the break, or report it precisely and stop. An irrelevant missing asset can block startup (a static dir the API never serves, a sample config). The generated skill may create it, mark it as verification scaffolding, and remove it in Cleanup.

3. `3-generate-the-skill`: Write `.agents/skills/verify-<app>/SKILL.md`, and lay the skill out as [project skill layout](../../references/project-skill-layout.md) says: helper scripts under the skill's `scripts/`, paths in `SKILL.md` relative to the skill folder, and the `.claude/skills` link made by the repository's setup step. Codex reads `.agents/skills/` directly. Claude Code reads it through the link.

   The frontmatter needs `name: verify-<app>` and a `description` that names the app, the surface, and when to use the skill. Without frontmatter the skill never registers. Give the body these sections. Ground each in what the interview found. Leave no placeholder.
   - **Launch.** The exact command that starts the app for verification, and how to tell it is ready (a log line, a prompt). Ready means usable, not only that a process answers: a database health check can pass while its init scripts still run. Launch reaches a usable state from an empty data dir, including migrations and seed data. Include teardown. A short-lived CLI or TUI has no server to keep alive. Its Launch builds the binary or installs dependencies once, and each drive starts in its own isolated PTY or tmux session.
   - **Doctor.** One read-only check that answers whether this instance is worth driving: process up, right version or build, port owned by us, auth valid. The agent runs it first, and again whenever anything looks off.
   - **Drive.** The harness recipe with this repo's real selectors and commands. Prefer stable handles (ARIA labels, data attributes, prompt strings, route paths) over coordinates and tab order.
   - **Evidence.** What to capture and where it goes. State these standards:
     - Exercise the real user path, not internal setters or test-only endpoints.
     - Capture the action and the resulting state, not only the final screen.
     - Verify side effects (files written, rows inserted, messages sent) next to what is visible.
     - Mock only where a production boundary already isolates the external system.
     - When the safe path is a dry-run or test mode, observe what it skips (files, network, git refs) instead of trusting its name. Some dry-runs still touch the network or open a browser.
   - **Cleanup.** How to tear down what the run created. Never kill by process name. Kill what you started. Cleanup removes instances and scratch state. Evidence survives cleanup, in a location the skill names.
   - **Helpers.** Every script the skill ships is in its `scripts/` folder and executable, and the skill body shows how to call it. A helper that the reader must reverse-engineer is not a helper.

4. `4-seed-the-feature-map`: Write `verify-<app>/features/README.md` and one file per user-facing feature. Start with the top three to five, found from routes, commands, menus, or docs. Follow the shape in [the feature-map example](references/feature-map-example/README.md). Each feature file has these four H2 sections: `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, and `Gotchas`. It answers four questions from the user's point of view: what the feature is, how to reach it, how to drive it, and what end state shows it works. When the seed data lacks a precondition that a journey needs, the journey reports a failure, and the reason goes in that feature's `Gotchas`. Never weaken a journey to make it pass. The map is the repo's source for verification, so a check that drives one entry point is incomplete when the map lists others.

5. `5-prove-the-generated-skill`: Run the skill's own instructions once, end to end: launch, doctor, drive one mapped feature, capture evidence, clean up. One feature is enough; the map exists so later runs cover the rest. After cleanup, confirm the evidence still exists at its named location. A cleanup that deletes the evidence fails this step. Fix what fails. Run the generated Cleanup after every failed attempt, so broken attempts strand no processes or ports. A generated skill that never ran is a draft, not a deliverable. If you ran it against a stand-in for the real target (a container for a fresh VM, a local stack for a remote one), list every setup step the stand-in did that the target will not do. Those steps stay unverified until a run on the real target covers them.

6. `6-hand-over`: Report the skill's path, the features the map covers, the feature you proved, and any unverified stand-in steps. Confirm that Git tracks every file of the skill folder and does not track the `.claude/skills` link. Confirm that `.claude/skills/verify-<app>/SKILL.md` resolves through the link after the setup step, or report the link as unverified. Tell the user that `/verification-skill` run again will audit the skill as the app changes. Suggest a cadence only if the user asks.

## Maintain mode

A feature map goes stale when the app changes. The unit of rigor is the feature, not every sentence: cover every feature file from source, and exercise every feature live.

Pick one outcome, and say which:

- **clean**: every feature got source and live coverage, and nothing is worth shipping. No branch, no PR.
- **changed**: proven corrections to the docs, harness, or map are ready to ship.
- **blocked**: coverage could not finish, or a proven fix could not ship safely. Say exactly what blocked it.

Edit only the verification skill's own folder: its `SKILL.md`, `features/`, and the harness scripts it owns. Never edit product code. A behavior the map describes that the app no longer has is either doc drift (fix the map) or a product regression (report it).

1. `1-clean-the-index`: Read the feature-map README and list its sibling files. Fix missing, extra, duplicate, and dead entries. Generate no inventory.

2. `2-run-the-source-wave`: Launch one read-only subagent per feature file, all at once. Each explains from source how the feature works, flags likely doc drift with citations, and returns one live recipe. A subagent never drives the app and never edits a file. Each returns: feature summary, source entry points, likely drift or "none", one recipe. Done when every feature file has a returned summary.

3. `3-reconcile`: Merge overlapping recipes into as few app states as practical. Spot-check cited drift. Do not re-prove claims that look clean. Sweep recent churn for user-facing surfaces that the map lacks. Call a surface missing only with a concrete source path.

4. `4-run-the-live-pass`: Run this pass even when the source looks clean. You own all driving. Follow the verification skill's own Launch model: one long-lived instance driven in series for servers and UIs, or a fresh isolated session per drive for short-lived CLIs. The skill's Launch section decides, not this one. Exercise every feature at least once. Hold three invariants for the whole pass, whatever fails:
   - Never drive an instance that you have not health-checked since it last did something surprising. Run Doctor before the first drive, on each fresh session when sessions are the unit, and after any failed drive. When Doctor cannot see the failure (a wedged UI state on a healthy process), reset to a known state or relaunch.
   - Evidence captured so far survives every cleanup. Check it at its named location. Do not assume it.
   - Nothing a drive started outlives that drive's use. Clean up the residue of failed attempts, whether the session is stuck, exited, or shared. For a shared instance, clean the residue and keep the instance.

   A Doctor failure that skill drift caused is drift. Fix it within the edit scope and retry once. Restart only what the fix invalidated. Only then call the pass blocked. Mark a feature `verified-unreachable` only with the concrete prerequisite (auth, entitlement, OS, external state) and the route you tried. If the map omits that prerequisite, that is drift. Re-drive every harness fix live before it ships. Do the final teardown after the last drive, including those re-drives. Evidence stays.

5. `5-triage`: Sort each finding:
   - Wrong or missing user-POV description: doc drift. Fix it.
   - Working behavior the harness cannot drive: harness gap. Fix it, and keep scripts executable with their call shown in the skill body.
   - App behavior that is broken: product gap. Record it for the user. Keep it out of the corrections, and do not hide it with a doc change.

6. `6-ship-or-stop`: For changed, re-read every changed file, then make one change set of proven corrections. Publish it as one PR only when the request or the user's standing instructions authorize publication, by the rules in [ship-pr](../ship-pr/SKILL.md). Otherwise leave the verified local edits and report their state. For clean or blocked, publish nothing. Report the outcome and the real coverage. Keep short run notes (features covered, unreachable prerequisites, confirmed drift, outcome) in a scratch location, and do not commit them.
