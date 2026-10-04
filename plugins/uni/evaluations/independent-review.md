# Historical independent review of the initial build

This review records the original `0.1.0` build. The user later clarified that
Uni should focus on questions, active recall, and exercises inside lessons.
Version `0.1.1` removes the retention engine and storage workflow discussed
below. These results are preserved as history and are not current runtime
capabilities or verification of the revised instructions. See the
[current build report](../BUILD-REPORT.md).

Reviewer scope: held-out scenario/rubric authorship, installed public CLI and
packaging checks, production read-only review, and scoring separate model
responses. The reviewer did not write tutor instructions, retention production
code, manifests, research summaries, or illustrative transcripts. Review dates
and learner responses are simulated where stated; no live learner store was used.

## Observed defects and repairs

- Fresh installation failed when `.agents/skills` did not exist. The installer
  treated Nushell's missing path type as a string. The packaging owner repaired
  this. The clean-project regression now passes.
- The shared contract allowed concise paraphrasing of stored first responses.
  The tutor owner changed this to verbatim raw responses, with concise summaries
  confined to checkpoint summaries.
- The mathematics authoring example called a valid differentiability argument
  faulty. The coordinator changed it to valid but underexplained shorthand and
  retained the useful justification task.
- The storage contract referred to a development fixture that is absent from
  the copied skill installation. The engine owner marked it development-only.
- `init` accepted an invalid supplied replay clock. The engine owner added aware
  clock validation before touching the path and covered rejection in the existing
  missing/corrupt/date contract test.
- The fading-study summary needed missing-data and comparison qualifications.
  The packaging owner added its completion/attrition limits and distinguished
  within-group gains from superiority over other instructional conditions.
- The first integrated smoke's final checkpoint load printed a corrected answer
  before reasking that target, but the transcript called the question unexposed.
  The review skill now explicitly warns that completed-work and misconception
  fields can reveal answers. Postpone that family or mark assisted practice;
  keep a neutral resume checkpoint and separate raw observations when appropriate.

## Runtime and packaging evidence

The reviewer ran the complete offline suite after the repairs:

```nu
with-env {UV_CACHE_DIR: /private/tmp/uni-uv-cache} {
  uv run --offline --no-project --with fsrs==6.3.2 python -m unittest discover -s plugins/uni/tests -v
}
```

All ten tests passed: six retention-owner store contracts, three reviewer package
contracts, and one reviewer installed-session integration contract. The integration
uses actual CLI subprocesses from another working directory after installing a
disposable copy. It creates a profile/item/checkpoint, preserves an assisted
first response without schedule advancement, resumes in a new process, records
independent delayed recall, deduplicates the exact retry, checks the saved due
date, and exports JSON and Anki content. All store paths and dates are simulated.
The first-response feedback boundary and current-session holdout policy are
explicit: post-answer correction does not erase initial forgetting; exposed
items remain due but must not be immediately reasked as independent retrieval.

Each reviewer permanent test was observed failing at its public boundary:

| Contract | Credible regression observed in a disposable package |
| --- | --- |
| Provider versions/catalog source integrity | Changed one provider version; paired-version test failed |
| Complete copied siblings and resource resolution | Removed the shared tutoring contract; installed-resource test failed |
| No partial install or overwrite on collision | Removed the collision guard; existing symlink collision test failed |
| CLI checkpoint persistence across sessions | Removed the checkpoint write; save returned success, next-process resume failed |

No production source was changed for these deliberate mutations. Raw records are
in ignored `artifacts/uni-build/packaging-mutations.json`,
`installed-mutation.json`, and `installed-workflow.json`. The engine owner also
retained mutation evidence for its six store contracts separately.

The coordinator observed native offline Claude manifest and marketplace
validation passing. Codex manifests/catalogs were parsed as JSON and checked
against repository invariants. This is package validation and a copied-layout
check, not proof of native host installation, discovery, or automatic activation.

## Targeted factual checks

The reviewer checked primary sources independently for a bounded selection:

- [Feynman's primary transcription](https://feynman.com/science/what-is-science/)
  supports the 1966 talk / 1969 publication chronology. It does not establish a
  standardized four-step protocol or educational efficacy.
- [The author-hosted worked-examples manuscript](https://www.danamillercotto.com/uploads/4/7/7/2/47725475/barbieri_et_al__2023__we_meta-analysis.pdf)
  supports the mathematics synthesis's 55 studies and 181 effects.
- [The institutional expertise-reversal record](https://www.pedocs.de/frontdoor.php?source_opus=34113)
  supports 60 experiments, 5,924 participants, and task/population qualifications.
  Its authors are Leonard Tetzlaff, Bianca Simonsmeier, Tabea Peters, and Garvin Brod.
- [The fading-study publisher full text](https://bpspsychub.onlinelibrary.wiley.com/doi/10.1111/bjep.12781)
  supports the added missing-data and comparison limits. Its abstract and
  discussion differ on prior-knowledge moderation, so the suite avoids a firm
  claim from that result.

This was a source spot-check, not a second complete literature review. Other
source-access levels remain those explicitly reported by the research lanes.

## Behavioral boundary

Generated JSON files named below are retained in the repository's ignored
`artifacts/uni-build/evaluations/` directory. The [evaluation guide](README.md)
links them. Authored scenarios/rubrics stay here, with input snapshots beside
the run outputs. Moving the outputs did not change their contents or scores.

Nineteen requests and separate rubrics were authored before the reviewer read
finished tutor instructions. They are separate from authoring examples. A
separate response-generation agent receives only requests and raw supplied
material, then explicitly loads the named copied skill and shared contract.
The nineteen actual candidate responses are in `candidates.json`; independent
scores are in `results.json`. Seventeen pass. Two are diagnostic continuations
that locate a proof error or misconception, then leave the learner one useful
repair task. They omit an explicit correction demanded by the original rubric.
The results retain that literal original-rubric failure and the reviewer's
partial interpretation separately, instead of changing the rubric or claiming
nineteen strict passes. No critical production defect is inferred from those
appropriate next-turn choices.

Two separately supplied stalled-learner continuations explicitly request
instruction. Their actual responses in `continuations.json` both pass the
unmet correction criteria and immediate explanation control; scores are in
`continuation-results.json`. The original responses are unchanged. All ten
recorded skill/shared-resource hashes match the disposable generator copy.
Nine still match the checked-out resources. The review entrypoint received
a later checkpoint-exposure clarification from the integrated smoke failure;
its original hash is historical and the fix gets a separate targeted regression.
The generator context is shared across
cases, not isolated per request. Per-question key preparation inside model
reasoning is not directly observable from final text.

The amended review entrypoint passes a separate targeted response regression:
when the simulated checkpoint has already displayed the only due answer, the
tutor postpones that family and records no invented attempt or schedule change.
The current loaded review/quiz/shared-contract hashes match checked-out files.

The integrated smoke retains actual tutoring responses and CLI outcomes through
topic intake, an independent diagnostic error, worked instruction, assisted
explanation, item creation, assisted review, next-day scripted recall, real FSRS
schedule, retry, pause, and future due selection. The initial final resume
printed a corrected answer from checkpoint history before asking that target.
That failure remains preserved and excluded. Four actual repair commands keep
raw observations in a separate archive, save/load only a neutral checkpoint,
and fetch learner-safe due output. The new final prompt contains no key and
stops unanswered. Fourteen accepted commands have exit zero: ten reused sound
earlier commands and four repair commands. This is an explicitly simulated
workflow, with no final response or learner-efficacy claim. No unresolved
critical defect remains from the scoped independent review.

Neither simulated learners, model next-turn responses, nor deterministic store
tests measure educational efficacy. Automatic skill routing, live client
discovery, actual delayed human recall, and broad transfer remain untested.
