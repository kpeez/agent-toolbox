# PreToolUse gate for the PR-body hook: start a runtime only when the Bash
# payload can name gh. The hook acts only on a command word that is `gh` after
# quote removal. In the JSON payload such a word shows as `gh`, or as `g`
# followed by `'` or `\` (`g''h`, `"g"h`, `g\h`, a line break inside the word).
# Shell builtins only: no process starts when the gate exits.
payload=
while IFS= read -r line || [ -n "$line" ]; do
  payload="$payload$line
"
done
case $payload in
*g[h\\\']*) ;;
*) exit 0 ;;
esac
exec <<EOF
$payload
EOF
root=${0%/*}/..
set -- "$root/skills/ship-pr/scripts/pr_body.ts" hook
. "$root/scripts/run-ts"
