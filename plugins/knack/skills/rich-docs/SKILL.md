---
name: rich-docs
description: Create or revise compact, human-reviewable technical documentation using Markdown-first structure and a constrained vocabulary of semantic rich blocks. Use for feature specs, implementation plans, architecture notes, experiment reports, model or dataset cards, evaluation summaries, PR recaps, and other documentation where comparisons, diffs, evidence, diagrams, or review decisions should be easier to inspect than vanilla Markdown.
---

# Rich Docs

Make technical documents easier to review without asking the authoring agent to
design a web page. Keep prose in Markdown and use semantic blocks only when they
add structure, evidence, or review behavior that Markdown cannot express well.

## Workflow

1. Identify the reviewer's questions before choosing presentation:
   - What changed?
   - Why was it chosen?
   - What evidence supports it?
   - Where did it regress or remain uncertain?
   - Can another person reproduce or approve it?
2. Use native Markdown for headings, prose, lists, task lists, simple tables,
   code fences, links, images, and equations.
3. Promote content to a rich block only when it adds at least one of:
   - machine-validatable domain structure
   - side-by-side or interactive review
   - stable annotation anchors
   - meaningful alternate exports
   - renderer-independent semantics
4. Prefer the smallest block that answers the review question. Do not compose a
   page from visual layout primitives.
5. Keep the source understandable without the renderer. Every rich block must
   have a deterministic plain-Markdown projection.
6. Verify source files with the target renderer or validator when one exists.
   Until then, do not place custom tags in ordinary `.md` files; use their
   Markdown projections instead.

## Authoring Contract

- Treat the format as constrained, non-executable MDX.
- Allow GFM/CommonMark plus registered semantic tags.
- Use PascalCase tags, literal attributes, and Markdown children.
- Put substantial content in children, not escaped attribute strings.
- Use closed enums and required fields; never depend on silent defaults.
- Limit custom-block nesting to two levels.
- Reject arbitrary HTML, CSS, JavaScript, JSX expressions, imports, exports,
  spreads, callbacks, and component definitions.
- Reject unknown tags, attributes, child combinations, and enum values.
- Keep presentation controls such as color, width, spacing, and alignment out of
  the document language.
- Prefer semantic blocks such as `Compare` over generic containers such as
  `Columns`.

Read [references/core-blocks.md](references/core-blocks.md) for the ordered core
vocabulary and canonical source patterns.

For applied ML, evaluation, data, model, or experiment documentation, also read
[references/applied-ml.md](references/applied-ml.md).

## Output Rules

- Lead with the conclusion or decision, then the supporting evidence.
- Use a block once when one view can answer the question; do not repeat the same
  evidence in prose, a table, and a chart.
- Caption evidence with what the reviewer should notice.
- Preserve provenance: source path, run, commit, dataset split, evaluator, sample
  count, and timestamp where relevant.
- Make missing evidence visible rather than filling it with guesses.
- Keep interactivity additive. Static export must preserve the document's meaning.
- Use standard Markdown tables unless cells require richer content or interactive
  filtering.
- Use task lists unless checked state is application data.

## Anti-Patterns

- Raw HTML as the normal authoring path
- Generic `Card`, `Grid`, `Stack`, `Row`, or `Badge` blocks
- Large JSON objects embedded in attributes
- Tabs that hide information required to understand the document
- Live queries or notebook execution during rendering
- Mutable views whose selected state cannot be represented in source
- A new block that merely restyles an existing Markdown primitive
- Adding a block before its schema, canonical example, validation, and Markdown
  projection are defined
