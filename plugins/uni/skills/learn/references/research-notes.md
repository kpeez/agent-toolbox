# Research notes

These are original construction notes, not source reproductions. The
[registry](source-registry.json) records access date, exact URLs, source type,
rights, and consulted editions. Research was accessed on 2026-10-03 by the
historical, learning-science, and integration lanes. The coordinator supplied
their evidence packets for consolidation. The packaging lane independently
checked the current skills documentation and the Miller-Cotto paper metadata.
An accessible page is not automatically licensed for redistribution.

## Historical methods

**Toeplitz's genetic approach.** The original article appeared in
*Jahresbericht der Deutschen Mathematiker-Vereinigung* 36 (1927), 88–100.
The [EuDML starting record](https://eudml.org/doc/145749) was blocked; the
[LVR biography](https://www.rheinische-geschichte.lvr.de/Persoenlichkeiten/otto-toeplitz/DE-2086/lido/5f0d6c8629f333.82381110)
corroborates the bibliography. We did not read the original German article.
The [2015 English translation](https://doi.org/10.1017/S0269889715000071)
by Michael N. Fried and Hans Niels Jahnke was consulted through its publisher
excerpt and metadata, not full text. It records a lecture delivered in 1926.

The [Chicago book catalog](https://press.uchicago.edu/ucp/books/book/chicago/C/bo5485725.html)
describes the book-length application. The English edition is 1963; the
consulted catalog is the 2007 reissue with David Bressoud's foreword. Catalog
and contents were accessible. A research lane also opened a third-party scan;
its reuse permission was not established, and the scan is not bundled or
treated as an authorized full-text source. Do not describe 1963 as the first
German publication.

The useful design proposal is to make a formal idea answer a meaningful
problem. It does not establish that discovery always beats instruction.
`learn-genetic` lets the learner try a tractable approach, investigates its
limits, and connects a new representation to those limits. Label a modern
teaching reconstruction explicitly. Do not invent historical motivations,
require centuries of rediscovery, or imply one formalism was inevitable.

**Lakatos-inspired repair.** The
[publisher frontmatter](https://assets.cambridge.org/97811071/13466/copyright/9781107113466_copyright_info.pdf)
verifies the original 1976 publication, edited by John Worrall and Elie Zahar.
We consulted the [2015 Cambridge Philosophy Classics catalog](https://www.cambridge.org/core/books/proofs-and-refutations/A11138AE31DB52797A6E4C3F1856E1CB)
and [preface summary](https://www.cambridge.org/core/books/abs/proofs-and-refutations/preface-to-this-edition/5EBD6238A6AB4050D394124CC208C0C0),
not the complete dialogue. The Euler-polyhedra setting concerns proof,
counterexample, and revised definitions. This is a philosophical account and
pedagogical inspiration, not a controlled evaluation of tutoring.

`learn-refute` makes assumptions explicit, finds the particular failing step,
and retests a repair. A bad proof does not make its conclusion false. A
mathematical counterexample and a surprising empirical observation have
different force. A probabilistic model can assign low probability to a real
outcome without being logically falsified by that outcome alone.

**Understanding and the named Feynman protocol.** Feynman's
[What Is Science?](https://feynman.com/science/what-is-science/) was a 1966 talk
published in *The Physics Teacher* in 1969. The full web transcription states
permission; the [AAPT account](https://www.aapt.org/Resources/RichardFeynman_100.cfm)
corroborates its provenance. It distinguishes explanatory understanding from
knowing names. Personal examples and a speech are not teaching-efficacy data.
It does not document a standardized four-step method.

Scott Young's [2011 announcement](https://www.scotthyoung.com/blog/2011/09/01/learn-faster/)
links to a [practitioner protocol](https://www.scotthyoung.com/learnonsteroids/learnfast.html)
and [two-page transcript](https://www.scotthyoung.com/learnonsteroids/grab/TranscriptFeynman.pdf).
The linked material asks for explanation, gap identification, source
consultation, and simplification. Its availability is not proof that Feynman
authored that exact sequence. `learn-feynman` is this suite's modern adaptation:
the learner explains and revises. An agent-written simple explanation is
instruction, not evidence the learner completed the exercise. Avoid speed
promises and keep simplicity compatible with technical accuracy.

## Learning science

**Guidance and attempts before instruction.**
[Alfieri et al. (2011)](https://doi.org/10.1037/a0021017) synthesized 164 studies.
Unassisted discovery compared poorly with explicit instruction; enhanced
discovery performed better than comparison approaches on average. Populations,
tasks, and support differed. Its [full manuscript](https://www.fisme.science.uu.nl/publicaties/literatuur/2011_alfieri_discovery_learning.pdf)
supports assisted exploration, not a universal winner for every lesson.
[Lazonder and Harmsen (2016)](https://doi.org/10.3102/0034654315627366) analyzed
72 inquiry studies and found benefits of guidance for inquiry activity,
performance, and learning. Age and guidance-type moderator evidence was
limited. The [institutional PDF](https://pure.rug.nl/ws/files/81069469/Meta_analysis_of_inquiry_based_learning_Effects_of_guidance.pdf)
has explicit reuse restrictions and is not distributed here.

[Sinha and Kapur (2021)](https://doi.org/10.3102/00346543211019105) qualifies
problem solving before instruction: productive failure depends on design and
consolidation. We use bounded attempts, then connect the learner's attempt to
the correct mechanism. Confusion itself is not progress. The assistance ladder
and initial two-stalled-attempt rule are engineering defaults; they are not
established constants from these studies.

**Examples, explanation, and fading.**
[Chi et al. (1989)](https://doi.org/10.1207/s15516709cog1302_1) studied how
students explained worked examples in problem solving. Differences in
self-explanation support probing the reason for selected steps. They do not
show that requiring narration after every step benefits every learner.
[Dunlosky et al. (2013)](https://doi.org/10.1177/1529100612453266) rated
self-explanation as having moderate utility, with practice testing and
distributed practice receiving higher utility across the reviewed evidence.

[Barbieri et al. (2023)](https://doi.org/10.1007/s10648-023-09745-1) synthesized
55 mathematics studies and 181 effects. Worked examples helped mathematics
performance on average. Correct examples were more effective than incorrect
or mixed examples; adding self-explanation prompts was not a reliable bonus
and negatively moderated effects in the included studies. This is not a
universal causal claim that explanation prompts harm learning. Use small
correct examples and targeted why-step questions, then check independent work.

[Tetzlaff et al. (2025)](https://doi.org/10.1016/j.learninstruc.2025.102142)
synthesized expertise-reversal experiments: support needs change with prior
knowledge, with substantial domain and population variation. Humanities
evidence remains less certain. Fade help based on demonstrated performance
and restore it when needed.
[Miller-Cotto and Medrano (2026)](https://doi.org/10.1111/bjep.12781), first
published online in May 2025, studied 114 sixth-graders on geometry homework
over three intervention sessions. Only 73 completed; about a third of
observations were missing and imputed. Fading showed the largest within-group
pre/post effects, but pairwise posttest differences were not significant.
Learning-gain contrasts with ordinary problem solving did not establish
superiority over the other instructional groups. The design lacks a
worked-example-only and a self-explanation-only comparison,
so component effects are not cleanly isolated. Its abstract and discussion
give inconsistent statements about prior-knowledge moderation. We do not use
that paper to assert a firm moderator result or a general fading guarantee.

**Feedback.**
[Wisniewski, Zierer, and Hattie (2020)](https://doi.org/10.3389/fpsyg.2019.03087)
reviewed 435 studies with 994 effects and over 61,000 learners. Average benefits
hid large variation by information and outcome. The research lane accessed
abstract and full-text material through indexed results, not a confirmed
direct full publisher fetch. Use specific information about the error and
what to do next; neither praise nor repeated prompts alone assure learning.

**Retrieval, spacing, and successive relearning.**
[Karpicke and Blunt (2011)](https://doi.org/10.1126/science.1199327) compared
retrieval with concept mapping using college science texts and later
short-answer, inference, and concept-map outcomes. Retrieval benefited these
tasks; it does not establish broad transfer to any domain. The
[Dunlosky review](https://doi.org/10.1177/1529100612453266) supports retrieval
and distribution across varied settings.
[Cepeda et al. (2008)](https://doi.org/10.1111/j.1467-9280.2008.02209.x), accessed
as abstract and metadata only, studied over 1,350 participants with retention
delays up to a year. The useful gap depends on the desired delay; there is no
one universal spacing interval.

[Rawson, Dunlosky, and Sciartelli (2013)](https://doi.org/10.1007/s10648-013-9240-4)
was accessed as abstract and metadata.
[Rawson and Dunlosky (2022)](https://doi.org/10.1177/09637214221100484) was read
in full publisher HTML. Successive relearning combines successful retrieval
with revisiting material across sessions. In Uni, keep
the initial answer separate from a corrected response. Long-term scheduling
belongs outside the lesson suite. Immediate reconstruction
after feedback is useful practice but cannot serve as delayed retention data.

**Interleaving and transfer.**
[Rohrer and Taylor (2007)](https://doi.org/10.1007/s11251-007-9015-8), available
as abstract and metadata, found a delayed advantage from mixed mathematics
problem types in a narrow college task. The
[Brunmair and Richter (2019) abstract](https://doi.org/10.1037/bul0000209)
summarizes 59 studies with material-dependent effects: stronger for visual
categories, smaller for mathematics, uncertain for texts, with blocking
sometimes better for words. Interleave when selecting between related methods
is the learning goal; retain initial support for unfamiliar procedures.

The [Pan and Rickard (2018) abstract](https://doi.org/10.1037/bul0000151)
summarizes 122 experiments. Retrieval-related transfer varied by task, with
weak or absent effects for some forms. `learn-transfer` asks the learner to
choose a method without its name, justify applicability, and mark the analogy's
limits. Record the observed new application separately from recall. None of
these sources validates this exact combined AI tutor or a broad mastery label.

## Retention and implementation

This section preserves sources consulted for an earlier retention-engine
design. The current scope is instruction, questions, active recall, and concept
exercises in chat. Anki handles long-term review outside Uni. The FSRS and import
sources below are unused background, not dependencies or operational guidance.

[Wozniak's Twenty Rules](https://www.super-memory.com/articles/20rules.htm)
is practitioner guidance, not twenty independent scientific laws. It helps
formulate answerable, limited review targets. Preserve meaning and context;
split overloaded prompts and repair ambiguous cards. These item-design choices
are reviewed against real responses rather than assumed effective by rule.

The [Anki FSRS documentation](https://docs.ankiweb.net/deck-options.html#fsrs)
was consulted for rating and retention/workload conventions. It does not
establish conceptual understanding or the efficacy of this tutor. Uni does not
assign scheduler ratings or retention targets.

[py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) and
[PyPI](https://pypi.org/project/fsrs/) supply the maintained implementation.
The version checked during the earlier design was `6.3.2`, MIT licensed,
requiring Python 3.10 or later. No library or retention engine is required
by the current suite.

[Anki's text import documentation](https://docs.ankiweb.net/importing/text-files.html)
was consulted for the earlier content-export proposal. Uni has no Anki import,
export, or collection-management workflow.

## Skill integration

The [current OpenAI skills guide](https://learn.chatgpt.com/docs/build-skills)
supports repository `.agents/skills`, follows symlink targets, and requires
`name` and `description` frontmatter. Explicit Codex invocation uses `$skill`.
It recommends plugins for reusable bundles. Uni ships eight conversational
skills and the explicit teaching-workspace skill through native plugin
installation. Shared references remain inside the plugin. Restart the client
if new skills do not appear; installed files alone do not establish live activation.

The [official subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents)
informs construction delegation, not a requirement for multi-persona tutoring.
The [AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
supports keeping project instructions scoped. Ordinary coding requests remain
outside these tutoring triggers. The
[Agent Skills specification](https://agentskills.io/specification) informs
metadata and local-resource validation. Documentation was read and paraphrased;
no complete source documentation is redistributed.

The suite adds no learner database, scheduling, or separate model API.
Prompts and responses stay within the chosen chat host. Behavioral checks,
simulated examples, host discovery, and real educational outcomes are different
verification boundaries and must be reported separately.
