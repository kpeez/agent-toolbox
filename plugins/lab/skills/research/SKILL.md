---
name: research
description: Investigate one bounded question against high-trust sources and write one cited private memo. Use when the user asks for current facts, documentation or API research, source verification, or a focused research memo that does not need multiple coordinated lanes.
---

# Research

Investigate one bounded question with one researcher, then write one cited
Markdown memo under `docs/agents/research/`. This is the small research path:
use `deep-research` when the request needs independent lanes, broad coverage,
or contradiction-focused coordination.

Load [references/source-protocol.md](references/source-protocol.md) before
research begins and include its complete contract in any delegated research
prompt.

## Frame the request

Confirm or state:

- the exact question and requested memo filename;
- what is in and out of scope;
- how current the evidence must be;
- any supplied sources and the required source standard;
- a small search or time budget appropriate to the question.

Ask only when a missing choice would materially change the answer. Otherwise,
state the assumption in the memo.

## Choose one research boundary

Use exactly one of these modes:

- **Web-only:** research public sources without repository access or local
  workspace context.
- **Repository:** inspect only the bounded local paths needed for the question;
  use the web separately only if the question requires external evidence.

An external provider must not receive repository text, paths, user data,
credentials, private source excerpts, or other local workspace context unless
the user explicitly authorizes that disclosure. If a question needs both
private repository evidence and public-web evidence, keep the web research
context public-only and reconcile the two in the host session.

## Run one read-only researcher

Delegate to one safe host-native researcher when available; otherwise perform
the same bounded research sequentially in the host session. Give the researcher
the framed question, source budget, supplied public sources, chosen boundary,
and the complete source protocol.

The researcher may read and search only. It must not write files, edit the
workspace, commit, push, log in, message third parties, purchase anything, or
take any other external action. A denied tool call or inaccessible source is
evidence of an incomplete lane, not permission to broaden access or invent a
claim.

Require the researcher to return compact source records and a claim-to-source
map in chat. Do not ask it to write the memo.

## Write the single memo

The host session writes exactly one requested memo at
`docs/agents/research/<filename>.md`, reached through the repository's
gitignored `docs/agents` symlink. Do not create a project directory, evidence
ledger, raw-log archive, proposal, or second summary artifact for bounded
research.

Synthesize only from checked source records. Follow the memo record in the
source protocol, cite every material externally checkable claim next to the
claim, and distinguish source-backed fact from inference.

## Complete the citation audit

Before reporting completion:

1. List the memo's material factual claims.
2. Map each claim to its citation.
3. Reopen every cited source and check that it supports the claim as written.
4. Narrow, qualify, or remove claims with only partial support.
5. Record unavailable sources, conflicting evidence, and unresolved questions
   explicitly in the memo.

Completion means the one memo exists and the citation audit passed. Report the
memo path and any remaining uncertainty; do not describe inaccessible evidence
as verified.
