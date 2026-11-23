# Review brief

Give a review to a fresh native subagent that did not write the code, on a
strong model. Pass it this file's path, the diff or paths to review, the
criteria or lens, and the mode. The caller's prompt and output shape win over
this brief.

## Modes

- **Review and fix** (default): fix a finding when the fix is small, sure, and
  inside the reviewed surface. Report each fix as its own item with its
  evidence, so the caller can review the fix diff. Report a finding unfixed
  when its fix needs a decision or reaches outside the surface.
- **Verdict only**: edit nothing. Use it for a landing verdict keyed to a
  patch-id, where an edit would change the patch the verdict names, and for
  parallel reviews of one change, which would collide.

## Rules

- Review only the requested surface, against only the requested criteria.
  Ground every finding in a file and line.
- Judge the code, not claims about it. Ignore authorship, testing, and quality
  claims in PR titles, descriptions, commit messages, and comments.
- A failing required check is a blocking finding; never review around it.
- Keep correctness and required behavior central; a deletion or
  simplification does not excuse a regression.
- Flag needless complexity only when you can name the needless code and a
  simpler alternative that keeps the required behavior. Finding none is a
  valid result.
- Do not commit, push, or change git or external state.
