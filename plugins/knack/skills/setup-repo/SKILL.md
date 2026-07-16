---
name: setup-repo
description: Set up a repo for the knack workflow — interview the user about the issue tracker and repo structure, then write the repo-root AGENTS.md, symlink CLAUDE.md to it, and set up the private specs and ADR directories. Use when setting up a new repo, or when the user asks to add AGENTS.md or CLAUDE.md to a project.
disable-model-invocation: true
---

# /setup-repo — Repo-Level Agent Instructions

Write the repo-root `AGENTS.md` every agent reads. It is a **thin delta** on
top of the user-level instructions (which carry the workflow spine and code
rules): repo commands, structure, and the Agent skills block. The block below
resolves the stack-dependent header programmatically; you ask about the rest,
confirm, then write — never clobber existing content.

`AGENTS.md` should
be compact, scannable Markdown with commands and conventions a future agent can
act on directly.

## Repo facts and resolved header

```!
cd "$(git rev-parse --show-toplevel)" 2>/dev/null
echo "repo: $(basename "$PWD")"
echo "origin: $(git remote get-url origin 2>/dev/null || echo none)"
for f in AGENTS.md CLAUDE.md CONTEXT.md CONTEXT-MAP.md docs/adr specs; do
    [ -e "$f" ] && echo "present: $f"
done
[ -L CLAUDE.md ] && echo "CLAUDE.md is a symlink -> $(readlink CLAUDE.md)"
grep -h '^Issue tracker:' AGENTS.md CLAUDE.md 2>/dev/null | sort -u
echo "top-level dirs: $(ls -d */ 2>/dev/null | tr '\n' ' ')"
echo
echo "--- AGENTS.md header, resolved (use verbatim) ---"
if [ -f pyproject.toml ]; then
    printf 'Format with `uv run ruff format`, then lint with `uv run ruff check`. Use `uv run ty check` for type checking.\n\n'
fi
if [ -f package.json ] && grep -q '"typecheck"' package.json; then
    pm=npm
    if [ -f pnpm-lock.yaml ]; then pm=pnpm; fi
    if [ -f yarn.lock ]; then pm=yarn; fi
    if [ -f bun.lockb ] || [ -f bun.lock ]; then pm=bun; fi
    printf 'Use `%s run typecheck` for type checking.\n\n' "$pm"
fi
if [ -f CONTEXT.md ]; then
    printf 'Check [./CONTEXT.md](./CONTEXT.md) for terminology questions.\n\n'
fi
if [ -d .changeset ]; then
    cat <<'EOF'
For user-facing changes, add a changeset to `.changeset`. Check all changesets there first to see if there are duplicates. We use `@changesets/cli`, but you can create/edit the file manually. Make all bugfixes `patch`, all new features or breaking changes `minor` (since we're pre-1.0). Use `package.json#name` for the name.

EOF
fi
echo 'When changing public-facing behavior, check `README.md` to see if the documentation needs updating.'
exit 0
```

## Process

1. **Present findings** from the facts above: what exists, what's missing,
   and the defaults you propose.
2. **Ask: issue tracker.** One question, default inferred from the facts —
   Linear if Linear MCP tools are available in the session, GitHub if
   `origin` points at github.com, local markdown otherwise. Options: GitHub /
   Linear (capture team or extras for the line) / local markdown / other
   (capture a one-line description). The answer becomes the `Issue tracker:`
   line that `/to-issues` reads — tracker mechanics stay in `/to-issues`'s
   references, never copied into the repo.
3. **Draft the Structure section**: 3–8 bullets mapping the top-level dirs to
   what lives in them. Inspect enough to annotate honestly; show the draft
   and let the user correct it.
4. **Confirm and write `AGENTS.md`**: the resolved header from the block
   above, verbatim, followed by the template below with Structure and Agent
   skills filled in. If `AGENTS.md` already exists, update the
   `## Agent skills` block in place and append missing sections — never
   overwrite or reorder what's there.
5. **Link, specs, and ADRs** — run as one block (idempotent):

   ```bash
   ln -sfn AGENTS.md CLAUDE.md
   : "${LLMOS_ROOT:?Set LLMOS_ROOT to the llmOS checkout}"
   mkdir -p "$LLMOS_ROOT/projects/<repo>/specs" "$LLMOS_ROOT/projects/<repo>/adr"
   ln -sfn "$LLMOS_ROOT/projects/<repo>/specs" specs
   mkdir -p docs && ln -sfn "$LLMOS_ROOT/projects/<repo>/adr" docs/adr
   grep -qx specs .gitignore 2>/dev/null || echo specs >> .gitignore
   grep -qx docs/adr .gitignore 2>/dev/null || echo docs/adr >> .gitignore
   ```

   If the facts show a real (non-symlink) `CLAUDE.md`, ask before replacing it.

6. **Report** what was written, skipped, and decided.

## Template (appended after the resolved header)

```markdown
## Structure

<3–8 bullets: `dir/` — what lives there, confirmed with the user>

## Agent skills

### Issue tracker

Issue tracker: <answer + extras, e.g. github — issues live in `owner/repo`, or linear>. Conventions: `/to-issues`.

### Triage labels

Canonical: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. <If the tracker uses different strings, map them here.>

### Domain docs

<Single-context layout: committed `CONTEXT.md` at the repo root plus ADRs under `docs/adr/` (a symlink into the shared llmOS vault). — or, when CONTEXT-MAP.md exists: Multi-context: `CONTEXT-MAP.md` points at per-context `CONTEXT.md` files.>

Before working in an area, read the ADRs that touch it. If your output contradicts one, flag it explicitly (_"contradicts ADR-0007 — but worth reopening because…"_) rather than silently overriding.
```
