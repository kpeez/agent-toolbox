#!/usr/bin/env bash
# Read-only worktree prune audit. Classifies every git worktree by size, age,
# merge state, uncommitted work, remote and PR state, and the newest Claude
# Code session that touched it. Prints a table sorted by size with a suggested
# bucket. It never deletes anything; deletion stays a gated step in the
# clean-worktrees playbook.
#
# Usage: worktree_audit.sh [-b|--base <ref>] [repo-path]
#   repo-path defaults to the current repository.
#   -b sets the ref the MERGED column checks against (e.g. origin/integration).
#   Without it the base is origin/HEAD, then origin/main, then origin/master.
#   origin/HEAD is the remote's default branch, not always the branch PRs
#   merge into; pass -b when they differ.
#
# Buckets: hold-wip (tracked uncommitted edits), hold-open-pr (open or draft
# PR), verify-recent-chat (a session touched it in the last 4 days), safe
# (merged into the base, or its PR is closed or merged), review (none of
# these).
#
# The session scan reads only this repository's Claude Code project folders
# under ~/.claude/projects/: the main checkout's and each worktree's.
set -u

base=""
while [ $# -gt 0 ]; do
	case "$1" in
	-b|--base) [ $# -ge 2 ] || { echo "error: $1 needs a ref" >&2; exit 2; }; base="$2"; shift 2 ;;
	-h|--help) sed -n '2,/^set -u/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
	-*) echo "error: unknown option: $1" >&2; exit 2 ;;
	*) break ;;
	esac
done

repo="${1:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -z "$repo" ] && { echo "error: not in a git repo; pass a repo path" >&2; exit 1; }
cd "$repo" || exit 1
git rev-parse --git-dir >/dev/null 2>&1 || { echo "error: not a git repo: $repo" >&2; exit 1; }

# The main worktree is the first entry; every other entry is a candidate.
main_wt=$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /, ""); print; exit}')

if [ -z "$base" ]; then
	for cand in "$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" origin/main origin/master; do
		[ -n "$cand" ] && git rev-parse --verify --quiet "$cand^{commit}" >/dev/null && { base="$cand"; break; }
	done
	[ -z "$base" ] && { echo "error: no base ref (origin/HEAD, origin/main, origin/master all missing); pass -b <ref>" >&2; exit 1; }
	echo "warn: no -b given; MERGED checks against $base" >&2
fi

# Fetch the base before the merge check, since -b may name a branch not
# fetched yet. Best effort: a stale base is fine for a first pass. The
# explicit refspec creates the ref even in a single-branch clone.
case "$base" in
origin/*) git fetch origin "+refs/heads/${base#origin/}:refs/remotes/$base" --quiet 2>/dev/null \
	|| echo "warn: could not fetch $base; MERGED may be stale" >&2 ;;
esac
git rev-parse --verify --quiet "$base^{commit}" >/dev/null 2>&1 || { echo "error: base ref not found: $base" >&2; exit 1; }

# PR state by branch, fetched once as "<head>\t#<number>/<state>" lines with a
# lowercase state. Empty when gh cannot read this repository's PRs.
prs=$(mktemp)
trap 'rm -f "$prs"' EXIT
if command -v gh >/dev/null 2>&1; then
	gh pr list --author "@me" --state all --limit 1000 \
		--json number,state,isDraft,headRefName \
		--jq '.[] | "\(.headRefName)\t#\(.number)/\(if .isDraft and .state == "OPEN" then "draft" else (.state | ascii_downcase) end)"' \
		> "$prs" 2>/dev/null || : > "$prs"
	[ -s "$prs" ] || echo "warn: gh returned no PRs; PR column is empty" >&2
else
	echo "warn: gh not found; PR column is empty" >&2
fi

# Claude Code keeps sessions in ~/.claude/projects/<slug>/*.jsonl, where the
# slug is the session's working directory with every character outside
# [A-Za-z0-9] changed to "-".
projects="$HOME/.claude/projects"
slug() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }
main_sessions="$projects/$(slug "$main_wt")"

mtime() { stat -c '%Y' "$1" 2>/dev/null || stat -f '%m' "$1" 2>/dev/null; }
day() { date -d "@$1" '+%Y-%m-%d' 2>/dev/null || date -r "$1" '+%Y-%m-%d' 2>/dev/null; }
search() {
	# search <dir> <pattern...>: list session files that contain any pattern.
	local dir="$1"; shift
	local args=()
	for p in "$@"; do args+=(-e "$p"); done
	if command -v rg >/dev/null 2>&1; then
		rg -l -F --glob '*.jsonl' "${args[@]}" "$dir" 2>/dev/null
	else
		grep -rlF --include='*.jsonl' "${args[@]}" "$dir" 2>/dev/null
	fi
}

now=$(date +%s)

echo "# base: $base"
printf "SIZE\tAGE\tMERGED\tDIRTY\tREMOTE\tPR\tLAST_CHAT\tBUCKET\tWORKTREE\n"

git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /, ""); print}' | while IFS= read -r wt; do
	[ "$wt" = "$main_wt" ] && continue

	size=$(du -sh "$wt" 2>/dev/null | awk '{print $1}')
	[ -z "$size" ] && size="?"
	head=$(git -C "$wt" rev-parse HEAD 2>/dev/null)
	head_ts=$(git -C "$wt" log -1 --format='%ct' HEAD 2>/dev/null || echo 0)
	age=$([ "${head_ts:-0}" -gt 0 ] 2>/dev/null && echo "$(( (now - head_ts) / 86400 ))d" || echo "?")

	# Squash-merged branches are not ancestors of the base, so PR state is the
	# real signal; the ancestor check only catches fast-forward and rebase merges.
	git merge-base --is-ancestor "$head" "$base" 2>/dev/null && merged=YES || merged=no

	# Tell real work in progress (tracked edits) from untracked scratch.
	porcelain=$(git -C "$wt" status --porcelain 2>/dev/null)
	if [ -z "$porcelain" ]; then dirty=clean
	elif printf '%s\n' "$porcelain" | grep -qv '^??'; then
		dirty="wip:$(printf '%s\n' "$porcelain" | grep -cv '^??')"
	else dirty="scratch:$(printf '%s\n' "$porcelain" | grep -c '^??')"; fi

	branch=$(git -C "$wt" symbolic-ref --quiet --short HEAD 2>/dev/null || echo "")
	if [ -z "$branch" ]; then remote=detached
	elif git -C "$wt" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
		[ "$(git -C "$wt" rev-parse "origin/$branch" 2>/dev/null)" = "$head" ] \
			&& remote=pushed \
			|| remote="ahead$(git -C "$wt" rev-list --count "origin/$branch..HEAD" 2>/dev/null)"
	else remote=no-remote; fi

	pr="-"
	if [ -n "$branch" ]; then
		found=$(awk -F'\t' -v b="$branch" '$1 == b {print $2; exit}' "$prs")
		[ -n "$found" ] && pr="$found"
	fi

	# Newest session that ran in this worktree, or that named its path in the
	# main checkout's sessions. Match the path followed by "/" or a quote, so
	# fix-48 does not match fix-482.
	last="-"; last_ts=0
	files=()
	wt_sessions="$projects/$(slug "$wt")"
	if [ -d "$wt_sessions" ]; then
		while IFS= read -r f; do files+=("$f"); done < <(find "$wt_sessions" -maxdepth 1 -name '*.jsonl' -type f 2>/dev/null)
	fi
	if [ -d "$main_sessions" ]; then
		while IFS= read -r f; do files+=("$f"); done < <(search "$main_sessions" "${wt}/" "${wt}\"")
	fi
	for f in ${files[@]+"${files[@]}"}; do
		ts=$(mtime "$f")
		[ -n "$ts" ] && [ "$ts" -gt "$last_ts" ] && last_ts=$ts
	done
	[ "$last_ts" -gt 0 ] && last=$(day "$last_ts")
	recent=$([ "$last_ts" -gt 0 ] && [ $(( (now - last_ts) / 86400 )) -le 4 ] && echo yes || echo no)

	case "$dirty" in wip:*) bucket=hold-wip ;; *)
		case "$pr" in */open|*/draft) bucket=hold-open-pr ;; *)
			if [ "$recent" = yes ]; then bucket=verify-recent-chat
			elif [ "$merged" = YES ] || [ "$pr" != "-" ]; then bucket=safe
			else bucket=review; fi ;;
		esac ;;
	esac

	printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
		"$size" "$age" "$merged" "$dirty" "$remote" "$pr" "$last" "$bucket" "$wt"
done | sort -t$'\t' -k1,1 -rh
