# bootstrap-project

Applies when: a request to set up a research project's `research-context` and first procedure skill. A missing `research-context` does not select it by itself; route the task on its own terms.

You own the project's starting kit: one `research-context` skill that is true, and the first procedure skill.

Read the repository before you write. Write only facts you checked in a file. Do not guess how the data arose. Mark each unknown as an open question for the user.

1-survey-the-repo: Read the data, the pipeline scripts, the results, the docs, and the shell history. List each recurring procedure with the command that runs it and where it runs. (research-skill)
2-write-research-context: Write the `research-context` project skill: data, variables, how the data arose, known confounds, and analysis conventions. Each statement names its source file. (research-skill)
3-prove-the-context: Answer three questions about the data from the skill alone, then check each answer against the files. Fix the skill for each wrong answer. (research-context)
4-rank-procedures: Rank the procedures by how often they run and how costly a silent error is. Show the ranking and name the top procedure. (encode-the-procedure)
5-codify-the-top-procedure: Run the playbook on the top procedure. A skill for it exists at the end. (codify-procedure)
6-list-the-rest: Record each remaining candidate in the "Procedure skills" list of `research-context`, marked as proposed. (research-skill)

Reply: research-context path, the three proof questions with results, the ranked procedures, the skill created, open questions.
