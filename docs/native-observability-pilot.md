# Native skill observability pilot

Updated 2026-10-06. This controlled pilot tests whether native traces can prove
complete skill delivery before an action. It does not measure natural skill
selection or task utility. Private raw captures, launch manifests, reservation
records and audit reports remain in ignored `artifacts/skill-evals/` storage.
Code pushes do not back up that storage.

## Observed evidence

| Surface | Observed result | Limit |
| --- | --- | --- |
| Codex exec JSONL, CLI 0.159.2 | Separate command start/result and terminal turn records | The first control used an unavailable `cat` command and stopped. It proved neither a filesystem denial nor skill delivery. |
| Claude stream JSON, CLI 2.1.286 | Native Read denied the outside canary; a subsequent result reconstructed the exact frozen skill bytes; the separate action Read started afterward | This is an explicit read control. It does not establish natural activation, complete injected context, effective effort or complete hook suppression. |
| Claude metadata control channel | Initialization succeeded and returned twenty enabled plugin skill rows, including skills absent from the command menu | The checker stopped before hook inspection because optional pending-status fields were not accepted. Retained metadata cannot distinguish omission from malformed values in that historical reply. |
| Corrected Claude metadata control, CLI 2.1.292 | Initialization and hook listing completed in 1.43 seconds; reported `allDisabled=true`, zero policy/listed hooks and zero validation errors | Omitted pending fields remain `not_reported` with null counts. This is observed metadata, not proof of every startup effect or complete hook suppression. |

The Claude control reported the requested `claude-sonnet-5-5` model. Its effective
low effort remains unknown. The Codex stream did not establish the served model
or effort. Requested settings and successful help commands are configuration
evidence only.

## Approved continuation and limits

The shared reservation ledger records four consumed attempts out of eight.
The optional-field checker was corrected and checked offline; its single
authorized Claude hook-inspection follow-up is complete and independently
audited. A corrected Codex control using `/bin/cat` remains in preparation.
Every startup consumes a new reservation; old attempts and failed gates remain
immutable. The metadata follow-up retained one filtered result file and no raw
stdout or stderr; its process group was verified gone.

Use the approved exact models, `gpt-6.1-sol` low and `claude-sonnet-5-5` low.
Runs are sequential, at most ninety seconds each, and subscription-only. No API
billing, paid extra usage, model substitution, global configuration edits,
installation or unbounded retries are authorized. Stop on a billing, privacy or
isolation contradiction. A larger benchmark needs a separate count and budget.

Keep the full competing skill catalog represented. Metadata replies must be
filtered before persistence. Omitted optional fields, malformed fields and
actual pending requests need distinct states. Missing telemetry stays unknown;
it must not become a pass or a skill-selection miss.

## Evidence contract

A verified load needs exact frozen resource identity, successful complete body
delivery, an auditable call/result link, and delivery completion before the
case-relevant action starts. Record raw byte/line references and coverage.
Partial reads, failed reads, mentions, catalog listings and model self-report
do not establish that contract. Child-agent evidence stays child-scoped.

Use isolated disposable fixtures and keep labels and expected answers outside
model-readable inputs. Validate actual tool boundaries; a read-only profile can
still allow reads outside the fixture. Codex named permission profiles must not
be combined with legacy sandbox settings; see the official
[permission profile documentation](https://learn.chatgpt.com/docs/permissions).

Hidden model inputs are a measurement limit, not a prerequisite for independent
immutable collection and replay. The existing seventy-case offline harness is
development evidence. No native activation baseline or paired utility result
has been established. Provider adapters and downstream scoring must advertise
only the capture surfaces and claims that their evidence supports.
