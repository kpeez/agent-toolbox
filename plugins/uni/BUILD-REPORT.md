# Uni build verification

Current version: `0.1.2`, revised on 2026-10-04 to bundle the existing `teach`
workspace workflow and four format templates with the eight conversational
skills. The moved files retain their content, upstream license, and
explicit-only invocation policy. Long-term scheduling remains external.

## Current verification

Native plugin installation replaces the optional custom skill-copy installer.
The retired installer tests protected its copy and non-overwrite behavior;
those contracts no longer belong to Uni. The hardcoded skill-count assertion
did not protect useful behavior. The remaining packaging invariants are checked
directly at release, without maintaining a Python test runner in this
instruction-only plugin.

Run the relevant offline checks from the repository root:

```nu
claude plugin validate plugins/uni
claude plugin validate plugins/uni/skills
claude plugin validate .claude-plugin/marketplace.json
```

Also parse both provider manifests, marketplace catalogs, and hooks as JSON.
Check matching versions, valid catalog paths, one Uni entry per catalog, and
bundled Markdown resource paths. Compare the moved `teach` files to their
pre-move Git blobs. Validate installed component discovery separately from
instruction correctness or educational outcomes.

Observed `0.1.2` release results:

- Native Claude validation passed for the plugin, all nine skills, and the
  marketplace catalog.
- Direct JSON checks passed for both catalogs, their plugin manifests and
  hooks, paired provider versions, and Uni's catalog entries. The inherited
  Claude-only mod entry follows the repository's current catalog rules.
- All 46 local Markdown resource links resolve within the skill bundle.
- All seven moved `teach` files match their pre-move Git blobs byte for byte.
- Disposable provider-version and missing-template faults were both rejected
  by the direct release checks. No production source was mutated.
- The generic skill validator passes the eight conversational skills. It
  rejects `teach`'s existing `argument-hint` and `disable-model-invocation`
  metadata because its allowlist does not cover those native Claude fields;
  native component validation passes them. The move preserves that metadata.

Local release-check output and negative-control evidence are retained in
ignored `artifacts/uni-teach-move/`. They are not part of the distributed plugin.

## Recorded verification of version `0.1.1`

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

These were instruction/package checks. The revised behavioral scenarios have
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
