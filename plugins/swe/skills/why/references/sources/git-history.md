# Source: git and gh history

The record most closely tied to the code: commit messages and diffs, PR bodies
and reviews, code comments, tests, in-repository decision records and
changelogs, and the files that changed together.

## Search

```bash
git log --follow -p -- <file>                 # full history through renames
git log -S '<exact text>' -- <file>           # commits that added or removed the text
git log -G '<regex>' -- <file>                # commits whose diff matches the pattern
git show <commit>                             # one commit with its diff
git log <old>..<new> -p -- <file>             # changes between two points

gh pr view <number> --json title,body,commits,comments,reviews
gh api 'repos/{owner}/{repo}/commits/<sha>/pulls'   # the PR for a commit with no "(#123)"
gh pr list --state merged --search '<term>'   # PRs by keyword

rg -n -C2 '(TODO|FIXME|HACK|XXX|NOTE)' <file> # notes near the target
rg -l '<symbol>' --glob '*test*'              # tests that name the target
rg -l -i 'architecture decision|\badr\b' --glob '*.md'  # decision records
```

## Read with care

- A squash merge hides the branch commits. The PR's `commits` field and its
  review threads hold them.
- A revert followed by a re-apply often carries the real reason in the second
  message.
- A test added in the same commit often names the case that motivated the
  change.
- A file that changed in the same commits shows coupling. It is not evidence
  of intent.
