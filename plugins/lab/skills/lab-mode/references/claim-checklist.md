# Claim checklist

Check a claim from a paper, a log, or your own run against every section that
applies. Record each failed check next to the claim.

## Source

- Follow the citation chain to the first report. Quote the table, figure, or
  appendix location, such as "Table 3, row 4".
- Look for citation drift: "as shown in [x]" where [x] shows a weaker or
  different result.
- Record the dataset, split, version, metric variant (exact match or F1, macro
  or micro), model size, and prompt or shot count. Compare each with your claim.
- Name the paper version. Check the first preprint, the latest version, and
  any errata or retraction.
- When the origin is out of reach, write "reported in [x], not verified at the
  origin". Follow the
  [source protocol](../../research/references/source-protocol.md).

Failed when: a summary cites only an abstract. A number has no table, row, or
setting. The text names no version.

## Scope

- List what was measured: setup, data, metric, models, items, and runs. Put
  the claim's verb and subject beside it.
- Reject "models" when the evidence covers one benchmark, scale, or language.
  Reject causal words on a correlational analysis.
- Separate probe from use. A probe shows that information is decodable. It
  does not show that the model uses it.
- Replace each suitcase word ("reasoning", "understanding") with the
  operational definition the metric uses. Rewrite the claim at the supported
  scope, and mark the rewrite as yours.

Failed when: a summary repeats the abstract's verb with no scope. A guess from
the discussion section reads as a finding.

## Comparison

- Count the tuning budget on each side: trials, search space, selection set.
- Match data, compute, model size, and training length, or state the gap. Match
  the eval protocol: prompt, decoding, shots, preprocessing, metric, split. A
  prompt template change can move a score more than the claimed gain.
- Find the strongest relevant baseline. Copied numbers come from other code
  and data: re-run them in the same setup, or label them "not comparable".
  Check that the ablation removes one part, not several.
- In your own work, tune the baseline first with the same budget. Record both
  budgets in the [decision](../../principle-write-the-decision-first/SKILL.md).

Failed when: "A beats B" lists no tuning budget for each side. Baseline
numbers cite another paper. The ablation changes more than one thing.

## Noise

- Find the run count and seeds behind each number. Compare the gap with the
  seed-to-seed spread. One run has no spread.
- Compute the test-set sampling error. For accuracy `p` on `n` items, the
  binomial standard error is `sqrt(p(1-p)/n)`. For `p` near 0.5 and `n = 500`,
  it is about 2.2 points. A 1-point gap is inside one standard error.
- On the same items, use a paired test: McNemar's test or a paired bootstrap.
- Count the comparisons. When only wins from many benchmarks or configs
  appear, ask for all results and correct for the count.
- Reject best-of-seeds reporting. Ask for the mean and spread over all seeds.

Failed when: a gap has no run count or spread. A claim rests on one seed. Your
own result changed a decision before you repeated the config with new seeds.
A gap below that noise floor is no evidence.

## Rivals

- Write each rival as one sentence: "the gain comes from X, not from the
  method".
- Check train/test leakage and benchmark contamination (test set in
  pretraining data). Look for a decontamination report or a newer held-out set.
- Check metric artifacts (a judge that prefers longer answers or one position,
  a reward the model can game), confounds (more compute, data, or size),
  selection, and regression to the mean.
- Check the eval code for a wrong label, a wrong split, or a scorer that
  accepts any output. Feed it a known answer, as in
  [simulate-before-you-trust](../../principle-simulate-before-you-trust/SKILL.md).
- Rule out each rival with an observation that would differ if it were true:
  a length-controlled judge score, a fresh test set, or an ablation at equal
  compute. When a rival stays open, write "consistent with the method, and
  also with X" and name the separating check.

Failed when: a conclusion has no rival beside it. A judge scores both sides
with its bias unchecked. The test set's training overlap is unknown.

## Contrary evidence

- Write the opposite of each supporting query: "fails to replicate",
  "revisiting", "limitations of", "negative result", "does not generalize".
  Use the same sources and depth.
- List the forward citations of each key paper. Read the follow-ups and
  replications. No follow-up after years is a finding.
- Read public peer reviews. Write the strongest version of the opposing claim.
  Dismiss it only for a named flaw in its evidence, or stronger evidence.
- Log each empty search with query, source, and date. Use the
  [source protocol](../../research/references/source-protocol.md).

Failed when: every query favors the hypothesis. A key paper has no forward
citation check. The notes list no empty searches.

## Raw data

- Sample with a recorded fixed seed, not by eye. Read at least a few dozen.
- For "A beats B", read cases where A wins, B wins, and both fail. Read the
  losses of your preferred side first.
- Read outputs where metric and judgment disagree. Each is a metric artifact
  or a label error until shown otherwise.
- Print the model's input after preprocessing, truncation, and templating.
  Print the raw output before parsing.
- For a paper, open its released data and code. When none exists, record that
  outsiders cannot check the claim.

Failed when: you state a conclusion about behavior and read zero examples. You
picked samples by hand. You cannot say what the model received.

## Provenance

- Write the record at run time. Link each number to the exact command, config,
  full commit SHA, data version or content hash, seed, and environment.
- Give each run its own folder. Never overwrite an earlier run.
- Label a number without provenance "unverified" until a rerun regenerates it.
  Grade a paper's number with
  [grade-the-evidence](../../principle-grade-the-evidence/SKILL.md).
- Run the regeneration test: rerun one recorded number from the record alone.
  A gap beyond the noise means the record is incomplete.
- In an experiment loop, use the [autoresearch](../../autoresearch/SKILL.md)
  ledger.

Failed when: a reported number cannot be regenerated. A result names no commit
or data version. Two runs share one output folder.
