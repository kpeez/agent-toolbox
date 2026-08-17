# Changelog — lab plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

## 1.3.0 — 2026-08-17

- Rewrite `/autoresearch` as a karpathy-minimal loop (ADR 0016): a short
  co-authored `program.md` approved in chat replaces the 30-label frozen
  contract; evaluator hashing, the resume protocol, and
  `scripts/validate_run.py` are deleted. The loop is linear — one worktree,
  one branch, keep advances, worse resets to the last best commit.
- Replace the TSV ledger with an append-only `results.jsonl` (fixed core keys
  plus per-run `metrics`) and a regenerated `summary.md`; the run record lives
  in `docs/agents/autoresearch/<tag>/` from setup onward (ADR 0017), with
  untracked `.autoresearch/<tag>/` in the worktree as the fallback.
- Default every run to a declared stop condition; "run until interrupted" is
  an explicit per-program opt-in. Retain Karpathy's original prompt under the
  skill's `references/`.
- Ship `scripts/ledger.py`, the skill's only script: a semantics-free
  append-only ledger primitive (`append` and `render` verbs, no update or
  delete) that assigns experiment ids, JSON-escapes records, hard-codes
  append mode so the ledger cannot be overwritten, and regenerates
  `summary.md`.

## 1.2.1 — 2026-08-12

- Guard `/autoresearch` against noise and metric overfitting: derive the
  minimum meaningful improvement from repeated baseline runs when budget
  allows, and re-verify the final kept commit (plus any program-named held-out
  check) before declaring the endpoint met on long programs.

## 1.2.0 — 2026-08-09

- Move bounded `/research` from SWE to Lab as an immediate breaking ownership
  transfer; callers must use `lab:research` after this release.
- Add `/deep-research` for bounded read-only lanes, retained evidence packets,
  deduplicated evidence, citation-audited synthesis, and explicit stop reasons.
- Make `/autoresearch` reproducible around an approved immutable `program.md`,
  frozen evaluator, measured baseline, candidate commits and rollback, and an
  append-only TSV ledger.
- Document Lab's four-skill surface and synchronize the Claude and Codex
  manifests at version 1.2.0.

## 1.1.1 — 2026-07-17

- Skill-quality pass: tighten `/autoresearch` wording and condense the
  data-viz Tufte-perception reference.

## 1.1.0 — 2026-07-16

- Inline documentation guidance in `/autoresearch` instead of pointing at the
  knack plugin's documentation skill; align its references with the knack
  skill-set revamp.
- Manifest resync as the llmos plugin joins both marketplaces.

## 1.0.0 — 2026-06-02

- Initial release: the research half of the old agentspec plugin, carved out
  as lab when the marketplace was renamed agent-toolbox. Ships
  `/autoresearch` (autonomous experiment loop with runs stored under a
  configurable artifacts root, defaulting to a gitignored `.autoresearch/`)
  and `/data-viz` (chart selection, color accessibility, review checklist,
  and Tufte perception references).
