# Lesson evaluation

`scenarios.json` contains learner requests and `rubrics.json` holds separate
scoring criteria. Most were authored independently before the initial tutor
instructions. The simplified revision removes the scheduler case and replaces
record-management language with conversation-based observations. Earlier raw
input snapshots remain with their run artifacts.

Run the named skill using its copied `SKILL.md` and required shared references.
Generate one next tutor turn and retain the actual response and loaded resource
hashes. Then score it against the separate rubric. A meaningful lesson check
asks whether the tutor leaves a real task for the learner, waits, responds to
their answer, and gives appropriate instruction or an exercise that probes the
concept. It must not invent a learner response or leak the answer before recall.

Generated responses, scores, and traces belong in ignored
`artifacts/uni-build/evaluations/`. This directory keeps authored scenarios,
rubrics, and written review. Record generator and reviewer independence.
Explicit loading, automatic discovery, model behavior, and learning efficacy
are separate claims. Uni has no persistence or scheduling runtime to evaluate.

The unchanged permanent checks protect public packaging and safe copied
installation. Their oracles are repository manifest/resource invariants and
the installer's non-overwrite contract. They were observed failing under
disposable-package mutations during the original review.

## Historical evidence

The [initial independent review](independent-review.md) applies to `0.1.0`,
including the now-removed engine. Its nineteen next-turn responses, seventeen
literal passes, two literal failures interpreted as partial diagnostic turns,
and two passing explanation follow-ups remain unchanged. The old checkpoint
regression and integrated retention simulation are historical only. Source
hashes identify their earlier snapshot; they do not validate current wording.

See [the current build report](../BUILD-REPORT.md) for revision-specific checks.
Neither synthetic responses nor packaging tests establish educational efficacy.
