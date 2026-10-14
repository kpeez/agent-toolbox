# build-prototype

Applies when: a throwaway sketch settles a design or behavioral decision, or an empirical fork you would otherwise ask the user about.

You own the design decision, not the code. The prototype is a throwaway instrument. The real build follows build-feature.

This playbook inverts the laziness protocol's smallest change and the usual verification bar. Speed beats polish. Code quality does not matter. Do not plan. The rigor is in picking the right design cheaply. Propose variations the user did not ask for. Throw an approach away and try another.

1-scope-the-decision: Name the one decision the prototype makes, such as a layout, an interaction, a density, a behavior, or a timing. No decision means no prototype, so route to build-feature.
2-gather-references: When the design space is open, search prior art, summarize themes, palettes, and layouts, and let the user pick directions. Skip when the direction is set.
3-build-throwaway: Build in an isolated scratch directory outside production source. Use the lightest stack that shows the idea, or the smallest script that exercises the question. No production framework, tests, or abstractions.
4-switch-between-variants: Put competing variants behind one labeled switcher, such as buttons or a keypress. (exhaust-the-design-space)
5-observe-on-surface: Screenshot and drive each visual variant, with the project's verification skill when one exists. For behavior or timing, log the timing or print the output. The observation is the test. (prove-it-works)
6-recommend-direction: Present the alternatives, tradeoffs, and a recommendation. Hand the chosen direction to build-feature, or to architect for its shape. (build-feature, architect)

Reply: the variants explored, the evidence (screenshots, or the observed output or timing), tradeoffs, your recommendation, and the scratch path. Say plainly that the prototype is throwaway. No PR.
