# Uni learning suite scope

Current scope: interactive lessons that include questions, active recall, and
exercises to deepen concepts. Package as the `uni` plugin for the Codex and
Claude Code marketplaces. Preserve the standalone `teach` skill.

## Decisions

- Keep eight sibling skills and one shared tutoring contract. The umbrella
  lesson uses the exercise types as needed; it does not require a fixed sequence.
- Ask one meaningful question or task, wait for the learner, then give feedback
  and adapt. Explain directly when requested or when prerequisites are missing.
- Use `learn-review` for drills on recent or user-selected concepts in chat.
- Leave long-term scheduling to the learner's existing Anki workflow. Uni has
  no review database, scheduler, runtime dependency, or Anki integration.
- Keep research sources with their access limits. Separate evidence for the
  instructional methods from untested claims about this combined AI tutor.
- Use Luna for exploration and Sol for writing, testing, and independent review.

## Scope correction

The initial local build included a SQLite/FSRS retention utility. On 2026-10-03,
the scope was narrowed to questions, active recall, and exercises inside lessons,
with long-term review handled externally. This supersedes the retention utility
design. The engine, storage contract, and engine-only tests are removed.
Previous engine verification is historical evidence, not a current capability.

See [the build report](BUILD-REPORT.md) for current checks and limits. Generated
run output stays in ignored `artifacts/uni-build/`; research notes contain
original summaries and links, not redistributed copyrighted source texts.
