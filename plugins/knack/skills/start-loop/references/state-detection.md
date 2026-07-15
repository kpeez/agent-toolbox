# State detection & resume

`/start-loop` keeps no state of its own. It recomputes the current state from
durable artifacts on every invocation, so a run survives context loss, a fresh
chat, or a different machine.

## Skip-detection order

Apply in order. An approved spec establishes the slug but does **not** bypass the
tracker-parent search.

1. **Explicit spec slug** in the argument — `specs/<arg>/SPEC-<arg>.md` exists → bind
   the slug; it overrides branch-name and mtime candidates. Continue detection
   from step 3 with that slug.
2. **Explicit tracker target** named in the argument (issue id/url) → fetch it. If
   it's a child, find its parent. Skip sharpen, spec, and publication; resume from
   tracker state.
3. **Approved spec** — `specs/<slug>/SPEC-<slug>.md` contains `<!-- knack:spec-approved -->`
   → skip `sharpen` and `write-spec`.
   - Complete header but no marker → ask: *"This spec has no recorded approval
     marker. Treat its current header as authoritative? Reply `approve` or
     `review`."*
   - Placeholders or unresolved sections remain → resume `write-spec`, don't treat
     existence as completion.
4. **Tracker parent** found by the immutable `<!-- knack-spec: <repo>/<slug> -->`
   marker → use it; skip `to-issues`. Never create a second parent.
5. **Parent without children** → resume `to-issues` against the existing parent.
6. **Children exist** → derive progress only from their states, dependency links,
   and latest comments; skip Done/excluded slices; resume the fan-out loop
   directly (no "begin implementation?" prompt — spec approval covered it);
   pause only on a blocking `ready-for-human` slice.
7. **No durable evidence** → start `sharpen`.

Title-only tracker searches are insufficient — renamed or similarly named features
collide. Bind the parent lookup to both repository identity and slug.

## Resume & idempotency

Every phase must be idempotent or rediscoverable.

| Failure point | Existing artifact | Resume at | Duplicate guard |
| --- | --- | --- | --- |
| During sharpen | Conversation, ADRs, `CONTEXT.md` | `sharpen` | No spec or gate assumed |
| After sharpen, before approval | Settled conversation | sharpen→spec gate | Require explicit approval again |
| During spec writing | Partial/unapproved `SPEC-<slug>.md` | `write-spec` | Reuse slug + existing file |
| After spec approval | Approval marker in `SPEC-<slug>.md` | `to-issues` (no gate) | Don't rerun sharpen or duplicate spec |
| During parent publication | Parent may carry source marker | inspect parent, then `to-issues` | Search marker before creating parent |
| Parent created, children absent | Marker-bearing parent | `to-issues` child creation | Reuse parent; create only missing children |
| Children partially created | Parent + some children | `to-issues` reconciliation | Match existing children before creating |
| After issues published | Parent + children | fan-out loop (no gate) | Don't republish |
| During implementation | Child state + latest comment | next unblocked child in `implement` | Reuse child id + current state |
| All children complete | Closed children | `COMPLETE` summary | No phase or gate repeats |
| Required phase skill missing | — | stop | Name the skill; do not improvise |
