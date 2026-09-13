# Code organization

This is the house architecture for a project with several related figures.
Adapt names to the project; keep the layering.

## Three layers

1. **`style.py`**: constants, rcParams recipe, `apply_style()`, `footnote()`,
   `save()`. The only place rcParams are set.
2. **Primitives** (`charts.py` or equivalent): `ranked_dot_plot`, `stacked_bar`,
   `frontier_scatter`, each taking plain rows (label, value, color, marker,
   emphasis) and returning a `Figure`. They know nothing about the evaluation
   schema.
3. **Adapters** (`plots.py`, `compare.py`): read the summary file, validate,
   filter and order rows, map them to primitive inputs, write PNGs. Thin,
   schema-aware, one CLI entry point via `typer` or `tyro`.

Project-specific mappings (which first-stage pairs with which second-stage,
label offsets, output names) live in the adapter or a benchmark script, never
in a primitive.

## One input file

Raw per-run outputs are the source of truth. A summary step reads an explicit
run list and writes one dated summary file that records where each row came
from (run id, commit, data version). The plotter reads that one file and plots
everything in it. Selecting a subset of runs happens at summary time, not in
the plotter. Provenance lives here, not in the figure.

## Output layout

Example from a two-population benchmark:

```
<out_dir>/
  <population>/headline.png
  <population>/table.png
  <population>/det.png
  <population>/scores.png
  training_progress.png      # population-independent figures at the root
```

PNG only, 300 dpi, through `save()`. Regenerate everything from the summary
file; never hand-edit a figure. Move superseded outputs to the trash, not `rm`.

## Tests

- One test per primitive, on synthetic rows, asserting the invariant it protects
  (the accent row is the focal one, rows keep one order across panels, exactly
  one outlined cell per row, no PDF written, paths land under the population
  folder).
- Adapter tests on synthetic summary files in `tmp_path`, never on real data
  and never with real subject identifiers.
- Guard tests: mixed populations raise, unknown entities raise, oracle rows
  reach no figure, nonfinite values raise.
- After a refactor that must not change output, assert byte-identical PNGs for
  that change only; do not keep the assertion as a permanent test, since
  rendering libraries legitimately change bytes.

Name tests by the invariant, never "smoke".

## Look at it

Rendering is part of the change. Open every regenerated PNG at the size it will
be shown and check for label collisions, clipped marks, empty space, and a
footnote that has fallen off the canvas. A test suite passing is not a figure
being right.
