# Uni build verification

Current local version: `0.1.1`, revised on 2026-10-03 to put questions, active
recall, and concept exercises inside lessons. The separate SQLite/FSRS utility,
storage contract, engine tests, and runtime dependencies were removed. Anki
remains the learner's separate long-term review tool.

Initial verification ran before publication and installation. It created no
real learner records. The existing standalone `teach` skill is unchanged.

## Current verification

The unchanged packaging tests cover paired provider versions, real catalog
paths, complete copied sibling resources, and refusal to overwrite existing
skills. The engine-only tests were removed with their implementation. No new
permanent tests are needed for the instruction-only scope correction.

Run the relevant offline checks from the repository root:

```nu
with-env {PYTHONDONTWRITEBYTECODE: "1"} {
    python -m unittest discover -s plugins/uni/tests -v
}
claude plugin validate plugins/uni
claude plugin validate .claude-plugin/marketplace.json
```

Observed results for this revision:

- All three unchanged packaging and safe-installation tests passed.
- All eight skill-creator validations passed.
- Native Claude plugin-manifest and marketplace validation passed offline.
- Both manifests and catalogs parse as JSON; paired versions, plugin paths,
  and installed sibling references passed the packaging invariant checks.
- All nineteen current scenario IDs have one matching rubric.
- A separate Sol reviewer found no actionable issues in the completed skills,
  shared contract, examples, README, packaging, and evaluation guidance. The
  reviewer confirmed that scheduler references are historical only and that
  ordinary lessons include learner tasks and respect explanation/help controls.

These are instruction/package checks. The revised behavioral scenarios have
not been rerun through the earlier model-response evaluation harness.

## Historical evidence

The initial `0.1.0` build passed ten deterministic tests and eight skill
validators. Nineteen model next-turn cases produced seventeen literal rubric
passes and two literal failures interpreted as partial diagnostic turns; two
explicit-explanation follow-ups passed. Those results apply to the earlier
instruction snapshot. They are not a rerun of this simplified revision.

The initial build also tested a retention engine and repaired a checkpoint
answer-exposure issue. Those capabilities have now been removed. The
[historical independent review](evaluations/independent-review.md) preserves
the original evidence and its limits. Earlier generated responses, scores,
hashes, and traces remain in ignored `artifacts/uni-build/`, including its
`evaluations/` directory. They are local artifacts, not Git-backed backups.

## Evidence limits

The source registry records 30 sources and all 28 originally requested starting
URLs with access and rights limits. The bundle contains original summaries and
links. Some sources were available only as excerpts, abstracts, or bibliography.
No copyrighted books or papers are bundled.

Package checks and explicit skill loading do not prove automatic routing or
native client activation. No real learner study, delayed human recall, broad
transfer, or educational efficacy has been measured for this combined tutor.
