---
name: pr
description: Group current branch diff into atomic commits, push, open a draft PR if missing, and write an HTML diff/rationale artifact into the associated spec. Use when ready to publish branch work.
---

# /pr - Group, Commit, Push, Draft PR

Bundle the committed + uncommitted changes on the current branch (or worktree) into small atomic commits, push, and ensure a draft PR exists. Write an HTML artifact into the spec directory that explains the logical groupings.

## Rules

- **Atomic PRs, atomic commits.** Imperative, conventional-style commit subjects (`feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- **PR title and body come from PLAN.md, SPEC.md, STATUS.md, linked issues, and the diff.** Do not create `commits.md` or `draft-pr.md` artifacts in the repo.
- **The HTML diff artifact lives only in `specs/<feature>/`**, which is gitignored. It is a private review aid, not a PR comment or repo artifact.
- **Never add agent attribution** (`Co-authored-by`, `Generated with`, etc.).
- **Draft PRs by default.** Mark ready for review only when the user asks.
- **Squash merge by default.** Do not switch merge methods without being asked.

## Command

### /pr [feature-name]

<steps>

<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/STATUS.md` was modified most recently; fall back to legacy `implementation.md` only when no `STATUS.md` exists; if no spec exists, continue without one and skip the HTML artifact step</step>

<step action="read-context">when `<feature>` resolved, read `specs/<feature>/AGENTS.md`, `PLAN.md`, `SPEC.md`, and `STATUS.md` for intent, scope, linked issues, and the desired PR slice</step>

<step action="resolve-base">determine the review base with `git merge-base main HEAD`; fall back to `master` only if `main` does not exist. Record `<base>` and `<branch>` (from `git rev-parse --abbrev-ref HEAD`)</step>

<step action="gather-scope">collect the full branch state:
    - committed diff: !`git diff --name-status <base>...HEAD`
    - uncommitted tracked: !`git status --porcelain`
    - untracked: !`git ls-files --others --exclude-standard`
Inspect file diffs with !`git diff <base> -- <file>` and !`git diff -- <file>` for working-tree changes</step>

<step action="group">cluster every changed file (and within-file hunks if needed) into logical groups. Each group is one coherent intent — one feature slice, one refactor, one fix, one docs/test pass. Avoid mixed-intent commits. Order groups so each commit leaves the tree buildable</step>

<step action="propose">print the proposed grouping: for each group, list the files/hunks, the commit subject, and a one-line rationale. Stop here only if the user previously asked to confirm; otherwise proceed</step>

<step action="commit">for each group in order:
    - stage exactly that group (`git add <paths>`, or `git add -p` for partial hunks)
    - commit with the imperative conventional subject and a short body when useful
    - do not include unstaged leftovers; verify with `git status` between commits</step>

<step action="push">push the branch with upstream tracking when missing: `git push -u origin HEAD`. If upstream is set, plain `git push`. Never force-push without explicit request</step>

<step action="ensure-draft-pr">check for an existing PR with `gh pr view --json number,isDraft,url,title`. If none exists, create a draft:
    - title and body derived from PLAN.md, SPEC.md, STATUS.md, linked issues, and the diff
    - `gh pr create --draft --base main --title "<title>" --body "$(cat <<'EOF'\n<body>\nEOF\n)"`
If a PR already exists, leave its state alone (do not flip draft/ready)</step>

<step action="write-html">if a spec exists, write `specs/<feature>/pr-<branch>.html` using the HTML Artifact format below. Overwrite on re-run. Include every logical group, its rationale, and its diff hunks</step>

<step action="update-status">append the PR number and URL to `prs` in `specs/<feature>/STATUS.md` frontmatter and the body if not already present. Then run `python3 core/skills/spec/scripts/spec-status.py --write` (or `spec/scripts/spec-status.py --write` from an installed skill copy)</step>

<step action="summarize">print the Summary in the format below</step>

</steps>

## HTML Artifact

Path: `specs/<feature>/pr-<branch>.html` (gitignored — never committed).

Self-contained, no external assets. Inline CSS. One section per logical group with the rationale and a syntax-colored diff. Use this skeleton (adapt content; keep it minimal):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PR: <branch> — <feature></title>
<style>
  :root { color-scheme: light dark; }
  body { font: 14px/1.5 ui-sans-serif, system-ui, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; }
  h1 { margin-bottom: 0.25rem; }
  .meta { color: #888; margin-bottom: 2rem; }
  .group { border: 1px solid #8884; border-radius: 8px; padding: 1rem 1.25rem; margin: 1.25rem 0; }
  .group h2 { margin: 0 0 0.25rem; font-size: 1.05rem; }
  .group .why { color: #888; margin: 0 0 0.75rem; }
  .files { font-family: ui-monospace, monospace; font-size: 12px; color: #aaa; margin-bottom: 0.5rem; }
  pre.diff { background: #1118; color: #ddd; padding: 0.75rem 1rem; border-radius: 6px; overflow-x: auto; font-size: 12.5px; line-height: 1.4; }
  pre.diff .add { color: #6ee7b7; }
  pre.diff .del { color: #fca5a5; }
  pre.diff .hunk { color: #93c5fd; }
  pre.diff .file { color: #fcd34d; }
</style>
</head>
<body>
<h1>PR: <pr-title></h1>
<p class="meta"><branch> &middot; base <base> &middot; <pr-url-or-"no PR yet"></p>

<section class="group">
  <h2>1. <commit-subject></h2>
  <p class="why"><one-line rationale: what intent this group serves and why these files are together></p>
  <div class="files"><file paths, comma-separated></div>
  <pre class="diff"><!-- emit diff lines, wrapping in spans:
       <span class="file">diff --git ...</span>
       <span class="hunk">@@ ... @@</span>
       <span class="add">+...</span>
       <span class="del">-...</span>
       (HTML-escape &, <, >) --></pre>
</section>

<!-- repeat <section class="group"> for each group -->
</body>
</html>
```

Diff source for each group: `git diff <base>...HEAD -- <files-in-group>` after the commits land (so the HTML reflects what was actually committed).

## Summary Format

```
## PR Summary
- **Branch**: <branch>
- **Base**: <base>
- **Commits created**: <n>
  - <sha-short> <subject>
  - ...
- **Pushed**: yes
- **PR**: <url> (draft)  // or "existing PR left as-is: <url>"
- **HTML artifact**: specs/<feature>/pr-<branch>.html  // or "skipped (no spec)"
- **STATUS.md**: updated, specs/STATUS.md regenerated
```
