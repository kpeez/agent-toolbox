# investigate-question

Applies when: a read-only question with a cited answer, including "why was this built this way".

You own the answer. Plan, route, write.

The work is read-only. It produces a cited explanation or a recommendation, not a code change. Do not run architect. When the answer leads to a code change, hand back to the user and route to fix-bug or build-feature.

1-restate-question: Restate the question and the evidence that would answer it.
2-map-with-how: Run how over the code paths that answer it. (how)
3-trace-rationale: When the question is "why", trace the rationale through history. (why)
4-note-throughput: Write `throughput checkpoint: n/a, read-only investigation`.
5-shape-the-answer: Give Overview, Key Concepts, How It Works, Where Things Live, and Gotchas. For a choice between alternatives, give a recommendation with a tradeoffs table. (how)
6-label-each-claim: Label each claim with its source and one confidence tier from the why skill. (why)
7-check-reply-prose: Apply the prose rules to the reply. (writing)

Reply: a cited answer with a tier on each claim, and what remains unknown. For "are we sure?", give your real judgment with reasons and push back on a wrong premise. No PR.
