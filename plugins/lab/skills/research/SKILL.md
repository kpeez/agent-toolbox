---
name: research
description: Produce one retained, cited memo for a bounded research question or explicit source audit.
---

# Research

Investigate one bounded question with one researcher, then write exactly one
cited Markdown memo. Use `deep-research` when the request needs independent
lanes, broad coverage, or contradiction-focused coordination. Ordinary quick
factual answers do not need this skill or a saved memo.

Write the memo under `docs/agents/research/` unless the project or user
specifies another location. Create subdirectories as needed, whether tracked,
ignored, or reached through an existing symlink.

Read [the source protocol](references/source-protocol.md) when gathering
evidence, defining source records, writing the memo, or auditing citations. It
owns record details; do not duplicate its full contract here.

## Frame the request

Confirm or state:

- the exact question and requested memo filename;
- what is in and out of scope;
- how current the evidence must be;
- supplied sources and the required source standard;
- a small search or time budget appropriate to the question.

Ask only when a missing choice would materially change the answer. Otherwise
state the assumption in the memo.

## Choose one research boundary

Use exactly one mode:

- **Web-only:** public sources without repository access or local workspace
  context.
- **Repository:** only the bounded local paths needed for the question; use the
  web separately only when the question requires external evidence.

An external provider must not receive repository text, paths, user data,
credentials, private source excerpts, or other local workspace context unless
the user explicitly authorizes that disclosure within the repository boundary.
If both private repository evidence and public-web evidence are needed, keep
web research public-only and reconcile it in the host session.

## Run one read-only researcher

Delegate to one safe host-native researcher when useful; otherwise run the same
bounded work in the host session. Give the researcher the framed question,
boundary, source budget, supplied public sources, and only the context required
for that lane.

The researcher may search and read only. It must not write files, edit the
workspace, commit, push, log in, message third parties, purchase, publish, or
take another external action. A denied capability or inaccessible source is
evidence of an incomplete lane, not permission to broaden access or invent a
claim. Require compact source records and a claim-to-source map in chat. Do not
ask the researcher to write the memo.

## Write the single memo

The host writes exactly one requested memo at
`docs/agents/research/<filename>.md` (or the chosen location). Do not create an
evidence ledger, raw-log archive, proposal, or second summary artifact for
bounded research.

Synthesize only from checked source records. Cite every material externally
checkable claim next to the claim it supports, and distinguish source-backed
fact from inference. Preserve contradictions, failed searches, unavailable
evidence, and uncertainty rather than filling gaps from memory.

## Complete the citation audit

Before reporting completion, apply the source protocol's citation audit. Narrow,
qualify, or remove unsupported claims and retain material uncertainty in the memo.

Completion means the one memo exists and the citation audit passed. Report the
memo path and remaining uncertainty; do not describe inaccessible evidence as
verified.
