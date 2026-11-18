# codify-procedure

Applies when: a request to turn a procedure that the user does not state in full into a new project skill: one done or corrected in this session, one the user only names, or one the user gives in part. A procedure that the user states in full goes to research-skill.

You own one procedure skill that a fresh agent can follow and verify.

Take commands from what ran, not from memory. A skill that was never followed end to end is unproven. Turn each user correction into a check that runs.

1-name-the-procedure: Write the inputs, the outputs, the decisions, and the real commands from this session. For a procedure that did not run in this session, write the commands the user gave or that the repository holds; step 3 proves them. (encode-the-procedure)
2-load-the-context: When no `research-context` skill exists, first run steps 1 to 3 of bootstrap-project. Then load the project's data facts and conventions from it. (bootstrap-project, research-context)
3-run-it-as-is: Run the commands on the current checkout. For a long pipeline, use the smallest real input that goes through every stage. When one breaks, fix it and record the fix. When you cannot fix it, report the break and stop. (research-skill)
4-collect-validity-checks: List the checks from `research-context`, from domain conventions with a source for each, and from each user correction. Each check is a command with a pass or fail result. (claim-checklist)
5-build-the-known-good-run: Build one run with a known answer: a small real input with its recorded expected output, planted data, or null data that must show no effect. Run it through the real code path and record the expected result. (simulate-before-you-trust)
6-write-the-skill: Write the project skill: the commands, the checks, the known-good run with its expected result, and the gotchas. (research-skill)
7-prove-the-skill: Follow the skill's own text, and nothing else, on real data. Include its known-good run. Fix each gap you find, then repeat until the run passes. (research-skill)
8-register-the-skill: Add the skill to the "Procedure skills" list of `research-context` marked live, or change its proposed entry to live. Check that Git tracks the skill folder and that each link in the skill resolves. (research-skill)

Reply: skill path, its checks, the known-good result, and what remains unproven.
