---
name: review
description: Review a specified pull request, diff, or implementation for actionable regressions and requirement gaps. Use for direct code-review requests; not implementation, publishing, architecture audits, or coordinating several reviewers.
---

# Review

Review the requested change without modifying it. Resolve the exact diff,
base, or implementation snapshot from repository evidence; ask only when
ambiguity would materially change what is reviewed.

Use the user's criteria and accepted requirements. When none are supplied,
review correctness, behavioral regressions, and meaningful verification.
Read surrounding callers and relevant tests where needed to assess impact.

For each potential finding, identify the affected scenario and observable
consequence, verify it against code and available evidence, and cite a precise
file and line. Report actionable issues introduced by, or directly relevant
to, the requested change. Label pre-existing findings separately when in
scope. Rank findings by impact.

Separate verified defects from questions and material evidence gaps. A clean
result is valid; never invent a finding to fill a quota. Report required-check
failures and distinguish known baseline failures from regressions.

When judging new or rewritten tests, apply
[testing-code](../testing-code/SKILL.md)'s behavioral-value criteria. Do not
require fresh red evidence for unchanged valuable tests.

Use the existing reviewer role when an independent review is useful or
required. Give it the exact snapshot, criteria, acceptance conditions, and
available evidence. One direct review does not require
[orchestrate](../orchestrate/SKILL.md).

Follow any caller-supplied response schema. Otherwise return findings first,
then relevant uncertainty or a concise no-findings result. Do not edit code,
change PR state, publish a comment, or merge without separate authorization.
