# match-visual-parity

Applies when: make UI pixel-exact equivalent, such as matching two implementations or migrating a styling system.

You own pixel-exact equivalence. The baseline is the spec. You do not touch it.

Verify equivalence by image diff, not by eye. Do not modify the harness, tamper with the baseline, or restructure a component to make a diff pass. If the baseline looks wrong, stop and ask.

1-establish-baseline: Before any migration, build a visual regression harness that screenshots the current component in each state, plus the target when you match two implementations. No baseline means no parity claim. (prove-it-works)
2-migrate-shared-primitives: Migrate shared primitives first as a blocking phase.
3-migrate-one-component: Migrate one component at a time. Parallelize across worktrees with one owner per component. (separate-before-serializing-shared-state, swarm)
4-diff-each-component: Diff each component against its baseline on the real surface, with the project's verification skill when one exists. A nonzero diff is a fail. Investigate the pixel delta and repeat until the diff is zero. (prove-it-works)
5-publish-draft-pr: Push per component or per safe batch, and update the draft PR when publication is authorized. (ship-pr)

Reply: the components migrated, the diff result for each, the baseline harness location, and what is left.
