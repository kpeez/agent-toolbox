---
name: align-swe-with-pstack
description: "Pull upstream pstack changes into the swe plugin since the pinned commit. Merge copied files directly, review modified files, then move the pin. Use when asked to sync, update, or align swe with pstack."
metadata:
  internal: true
---

# Align swe with pstack

swe adapts Lauren Tan's pstack (`cursor/plugins`, folder `pstack`).
[upstream.json](upstream.json) is the sync record. It holds the pinned
upstream commit and one item for each pinned pstack file or folder:

- `copied`: the swe file keeps the upstream lines. Only a few host terms
  differ. A three-way merge applies upstream changes.
- `modified`: swe rewrote the file (Simplified Technical English, 80-column
  wrap, swe names, Claude Code and Codex terms) or merged it into other files.
  `local` lists every swe file that holds its content.
- `dropped`: swe does not use it. A path that ends in `/` covers its folder.

The script [scripts/pstack_sync.py](scripts/pstack_sync.py) clones upstream
into `artifacts/pstack-upstream` on first use (`--upstream` sets another
path). Run it from the repository root.

## Steps

1. `1-check-the-record`: Run `python3 .claude/skills/align-swe-with-pstack/scripts/pstack_sync.py check`.
   Fix each problem before you continue. Below, `pstack_sync.py` means this
   script path.
2. `2-list-changes`: Run `pstack_sync.py status`. It lists the upstream
   commits since the pin and each changed file with its class. Read the commit
   subjects first. They give the intent of each change.
3. `3-merge-copied`: Run `pstack_sync.py merge`. It writes each clean merge.
   It leaves a file unchanged when its merge conflicts or upstream deleted it.
   Review each such file as `modified` in step 4.
4. `4-review-modified`: Run `pstack_sync.py status --diff`. For each
   `modified` file, read the upstream diff and the swe files in `local`.
   Decide for each change:
   - **Port** it when its intent applies to swe. Write it in the swe file's
     style. Keep swe names, swe host terms, draft-first PRs, and swe decisions.
   - **Skip** it when it is Cursor-only, already in swe, or conflicts with a
     swe decision.
   Keep this review brief. Port the intent, not the upstream wording. Write
   one line per file: ported or skipped, and why.
5. `5-classify-new`: For each `new` file, import it (add an item) or drop it
   (add a `dropped` item). For a deleted upstream file, delete its swe content
   or keep it as swe-only, and remove its item. Ask the user before you import
   a new skill or playbook.
6. `6-move-the-pin`: Run `pstack_sync.py pin`. It writes the new commit to
   `upstream.json` and to the README Credits link. Then run `check` again.
7. `7-ship`: Bump the swe patch version in both plugin manifests. Run the
   checks that `AGENTS.md` names for the changed files. Open a draft PR with
   the `ship-pr` skill. List the upstream commit range and the step 4 lines
   in the PR body.

## Rules

- Keep the Credits entry for pstack in `README.md`.
- When a merge or review changes a file into or out of the `copied` shape,
  change its class in `upstream.json`.
- When a swe change moves pstack content to another file, update `local`.
