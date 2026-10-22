# Design notes

These notes give the sources for the tech-tree rules and their limits. Read them for rationale, not on every turn. Page numbers refer to Justin Skycak, *The Math Academy Way* (working draft, 2026), at <https://www.justinmath.com/files/the-math-academy-way.pdf>.

## Rules and sources

| Rule | Source |
| --- | --- |
| A topic is one narrow lesson with 3-4 KPs; a KP is one worked example and 2-5 questions | p. 74, 397 |
| At most 3-4 direct prerequisites; more means the topic is too big | Skycak, ["The most important thing to understand about building educational knowledge graphs"](https://www.justinmath.com/the-most-important-thing-to-understand-about-building-educational-knowledge-graphs/) |
| New lessons only from the knowledge frontier | p. 79, 212; knowledge space theory "outer fringe" (Falmagne & Doignon, [arXiv 1511.06757](https://arxiv.org/abs/1511.06757)) |
| Answer order matters in grading | p. 414 |
| Remediation ladder: more questions, rest and retry, key-prerequisite reviews, prerequisite lessons | p. 75-76, 300, 417 |
| No repeated re-explanation; do not lower the bar | p. 299, 418 |
| Placement: a pass credits ancestors, a fail debits descendants; barely placed topics are conditional | p. 375-381 |
| Learners overestimate what they know; do not use self-ratings | p. 463 |
| A prerequisite is not always encompassed; review credit flows only on encompassing edges | p. 78, 366-368; Skycak, ["Individualized spaced repetition in hierarchical knowledge structures"](https://www.justinmath.com/individualized-spaced-repetition-in-hierarchical-knowledge-structures/) |
| Prefer lessons that also cover due reviews; at least one lesson per about three reviews | p. 258-262, 314, 406 |
| Reviews without notes or worked examples in view | p. 337, 412 |
| Explicit instruction and worked examples for new topics | p. 139-146; Alfieri et al. 2011 (d = 0.38 against unassisted discovery); Barbieri et al. 2023 (g = 0.48 in math) |
| Retrieval and spacing | Rowland 2014; Adesope et al. 2017; Cepeda et al. 2006, 2008 |
| Mixed review after first mastery | Rohrer et al. 2020; Brunmair & Richter 2019 |

## Engineering choices

These values are not from a source. Change them when evidence from a learner says so.

- Pass rule: 2 consecutive correct answers without help per KP, within 5 questions. The book gives "2-5 questions" and no fixed threshold.
- Review intervals: 1, 3, 7, 14, 30, 60 days.
- Encompassing weights: only 0.5 and 1.0. Math Academy tunes finer weights by hand over thousands of topics.
- Credit that arrives earlier than half the current interval before the due date counts for nothing. Math Academy discounts early credit; this is a coarse version.
- An agent drafts the graph and a fresh reviewer audits it. Math Academy's experts build the graph by hand.

## Limits

- No independent controlled study of Math Academy exists. Its outcome reports are self-reported, with selected students.
- Mastery learning gives about 0.5 SD on curriculum-aligned tests (Kulik et al. 1990) and near zero on standardized tests in group-paced K-12 classes (Slavin 1987). Bloom's "two sigma" does not replicate (von Hippel 2024).
- LLM-drafted prerequisite graphs reach about 0.70-0.76 F1 against experts. Most errors are reversed or weak edges. Hard gating turns a wrong edge into a blocked subtree, so the review step and ladder step 5 matter.
- The script has no per-learner speed model, no population statistics, and no timing signal.
