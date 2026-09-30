# Interface design: design it twice when useful

When a consequential interface has materially different plausible shapes,
compare them before committing. This applies to new modules and chosen
deepening candidates. A bounded, obvious interface needs no alternatives.

## Frame the problem

Identify representative callers and the constraints every design must meet:
invariants, ordering, error modes, configuration, and performance. Classify
dependencies with [DEEPENING.md](../improve-codebase-architecture/DEEPENING.md)
when a refactor crosses an existing seam. A small code sketch can make the
constraints concrete; it need not be a proposal. Show the frame to the user
when feedback could materially change the design.

## Compare designs

Generate the smallest useful set of materially different interfaces. Favor a
small caller surface, required variation, and a simple default path. For each
design, show:

1. The interface, including types, invariants, ordering and error behavior.
2. A representative caller use.
3. The behavior hidden behind the interface.
4. How side effects and dependencies cross the seam, where relevant.
5. What the design makes easier and what it asks callers to know.

Generate alternatives directly for a bounded design. Delegate independent
alternatives only when breadth or decision cost justifies it.

Present the designs sequentially, then compare depth, locality, seam placement
and costs. Recommend one and explain why. Combine elements when a hybrid better
serves the actual callers.
