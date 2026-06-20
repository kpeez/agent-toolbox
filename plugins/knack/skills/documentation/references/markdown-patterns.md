# Markdown Documentation Patterns

Use these patterns in ordinary Markdown. They should work in GitHub, common
editors, issue trackers, and most static documentation tools.

## Write For The Next Action

Choose the structure from what the reader needs to do next:

| Reader needs to | Best structure |
| --- | --- |
| approve a plan | Decision, scope, risks, verification |
| implement a slice | Behavior, acceptance criteria, scope, blockers |
| review a PR | Summary, commit/story map, verification, risks |
| resume work | Current state, done, next, gotchas, commands |
| understand a choice | Context, decision, alternatives, consequences |
| debug later | Symptom, repro, cause, fix, regression check |

## Strong Sections

### Summary

Use 2-5 bullets. Say what changed, what matters, and what remains risky.

### Context

Explain only the minimum background needed for this document. Link out instead
of re-explaining settled context.

### Scope

Use explicit in/out boundaries:

```md
## Scope

- In: parser errors for malformed task frontmatter
- Out: tracker API retries, UI display changes
```

### Acceptance Criteria

Make every criterion observable:

```md
## Acceptance Criteria

- [ ] Invalid frontmatter returns a clear parse error
- [ ] Valid legacy issues still parse without changes
- [ ] The parser test suite covers missing, unknown, and malformed fields
```

### Verification

List exact commands and observed results. For unfinished work, say what still
needs to be run.

```md
## Verification

- `uv run pytest tests/test_parser.py` -> passed
- `python examples/parse_legacy_issue.py` -> passed
```

## Useful Markdown Tools

### Comparison Tables

Use for alternatives, before/after states, or reviewer trade-offs.

```md
| Option | Strength | Weakness | Decision |
| --- | --- | --- | --- |
| Keep JSONL | easy diffs | weak typing | reject |
| Move to Parquet | typed, queryable | preview tooling needed | accept |
```

### Diffs

Use fenced `diff` blocks for short code, config, prompt, or docs changes.

```diff
- retries: 1
+ retries: 3
+ retry_backoff_ms: 250
```

For larger diffs, link to the file or PR diff and summarize the intent.

### File Trees

Use fenced text for proposed or changed structure.

```text
src/eval/
|-- scorer.py        # slice-aware aggregation
|-- calibration.py   # expected calibration error
`-- test_scorer.py   # regression coverage
```

### Diagrams

Use Mermaid only when a diagram clarifies flow better than prose. Keep it small.

```mermaid
flowchart LR
  RawData --> CleanData --> Train --> Evaluate --> Report
```

### Details Blocks

Use HTML `<details>` sparingly for long logs or optional evidence. Do not hide
information required to understand the main argument.

````md
<details>
<summary>Command output</summary>

```text
...
```

</details>
````

### Links And File References

Prefer precise links to paths, issues, PRs, ADRs, and commands. Avoid stale line
numbers in tracker issues unless the line is the object of review.

## Style Rules

- Prefer concrete nouns and verbs over process narration.
- Cut filler such as "This document explains" and "In order to".
- Use numbered steps only for actual sequences.
- Use tables only when readers compare rows or columns.
- Keep examples short and runnable.
- State assumptions and uncertainty explicitly.
- Do not duplicate the same information in prose, a table, and a list.
- Do not bury decisions after long background sections.
