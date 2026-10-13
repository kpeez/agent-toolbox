# Verdict brief

Give this brief to an agent that did not write or edit the branch, such as a
fresh [reviewer agent](../../../agents/reviewer.md). Fill each `<field>`. Its
caller contract lets this brief set the verdict shape.

```text
Judge pull request <pr> for landing. Base <base-sha>, head <head-sha>.
Read the patch with: git diff <base-sha>...<head-sha>

Claims to check:
<each behavior the PR claims, with the evidence the PR body gives for it>

Criteria:
- Each claim holds in the code, and the evidence shows it on the real entry
  point.
- The patch does nothing outside its claims that a reviewer would need to know.
- Required checks at <head-sha>: <state from gh pr checks>.

Run read-only commands that exercise the claimed behavior when they exist.
Name each check you could not run.

Reply in this shape and nothing else:
VERDICT: PASS | PASS+NOTES | FAIL
HEAD: <the head SHA you judged>
FINDINGS:
- <file:line> <finding> (blocking or note)
```

PASS and PASS+NOTES both pass the landing gate. A FAIL, or a `HEAD` line that
differs from `<head-sha>`, does not.
