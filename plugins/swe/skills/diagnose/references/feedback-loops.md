# Feedback loops

Use this reference when the diagnosis needs a specialized or repeated signal.
Choose the smallest evidence source that distinguishes the leading hypotheses;
do not build a harness merely to follow a fixed ranking.

## Useful forms

- A failing test or example at the seam that reaches the bug.
- An HTTP or CLI invocation against a running system, compared with known-good
  output.
- A headless browser script that asserts the affected DOM, console, or network
  behavior.
- Replay of a captured request, payload, event log, or trace.
- A throwaway harness over the smallest real subset of the system, with only
  true external dependencies substituted.
- A property or fuzz loop for a wrong-output class with a real independent
  oracle.
- A bisection harness across commits, datasets, versions, or configurations.
- A differential loop comparing old and new behavior or two configurations.

## Make the signal useful

Iterate on the loop itself: cache setup, narrow the scope, assert the specific
symptom, pin time and randomness, isolate the filesystem, and freeze network
inputs when appropriate. A short deterministic loop is valuable; a long flaky
one needs either a higher reproduction rate or an explicit limitation. When a
check passes too easily, suspect the observation method before the system.

For intermittent bugs, loop the trigger, add targeted stress, or narrow the
timing window. A unique prefix on temporary debug logs can make cleanup
auditable.

## Performance

Before you trust, report, or act on a measured number, follow
[explain-the-number](../../principle-explain-the-number/SKILL.md).

Choose a fix from the cheapest form first, and stop at the first form that
meets the target:

1. Do not do the work. Stop work whose result nothing uses.
2. Do the work once, not again.
3. Do less of it.
4. Do it later.
5. Do it while nothing waits for it.
6. Do it concurrently.
7. Do it cheaper.

## Static-checker diagnostics

For a linter or type-checker false positive, or a suppression you want to
delete because an upstream fix supposedly shipped:

- Reproduce under the project's own config, not tool defaults. A bare file
  outside the project runs under the tool's default preset, which can disable
  the very check you are chasing and read as "already fixed". Run the repro
  inside the project or pass its preset explicitly. For example, pyrefly 1.5
  checks a file outside any configured project with its `basic` preset, which
  skips checks that a project with `[tool.pyrefly]` runs at `default`. Pass
  `--preset default` to match.
- Confirm the latest version from the package registry (for PyPI,
  `https://pypi.org/pypi/<pkg>/json` gives `info.version`); a tracking issue's
  "latest is X" goes stale. Then bracket the regression with a version sweep,
  `uvx <tool>@<version> check <repro>`, across last-known-good, first-bad, and
  the candidate, pinning the preset on every run. Run the binary; release
  notes may not mention the regression.
- Confirm a "fixed in the new version" claim on the real surface: in a
  worktree, delete the suppression comments, run the project's own check
  command, then restore them. Delete a suppression only when that run is clean.
- Use `reveal_type` to expose binding and descriptor bugs: reveal the member on
  the class and on an instance. If instance access still carries a `self` or
  first parameter that class access has, the descriptor binding did not fire.
- Isolate the trigger with control repros that remove one factor at a time
  (the decorator, the overload, the inheritance). The intersection that still
  fails names the mechanism.
