# Edge review brief

Give this brief and the `tech-tree.json` path to a fresh reviewer. Do not give it your reasons for the graph beyond the file.

---

You review a course prerequisite graph before any lesson exists. A wrong edge blocks a learner from a whole subtree. A missing edge sends a learner into a topic they cannot do.

Read `tech-tree.json`. For each topic, read its goal, check, KPs, and `requires` reasons. Report only problems, as a list. For each problem, give the topic id, the kind, one line of evidence, and the fix.

Kinds:

- **Reversed edge.** B is the prerequisite of A, not A of B.
- **Weak edge.** A learner can pass B's check without A's skill. The reason names a loose relation ("related to", "context for").
- **Missing edge.** B's check or a KP uses a skill that no ancestor teaches.
- **Wrong key prerequisite.** A KP's `key` list omits a topic the step uses directly, or lists one it does not use.
- **Too big.** The goal holds two skills, the check tests two skills, or the topic needs more than 4 direct prerequisites. Name the split.
- **Wrong weight.** An `encompasses` weight claims practice that B's problems do not give. A prerequisite used only as background gets no weight.
- **Bad check.** The check is not concrete, cannot be graded, or tests more or less than the goal.

Do not rewrite the graph. Do not report style. Say "no problems found" if there are none.
