---
name: reflect
description: "Run three parallel reviewers over this session's transcript, surface durable learnings, and route each to a concrete skill edit or a structural fix."
disable-model-invocation: true
---

# Reflect

Mine the current session for durable learnings, then route them into skill
edits or structural fixes.

Skip when the session is trivial, off-topic, or already covered by a skill
the agent followed correctly. A one-off is not a learning.

## 1. Locate the active transcript

Find this session's transcript before you fan out. Read only this project's
transcripts. Never glob across `~/.claude/projects/*/` or all of
`~/.codex/sessions/`. That crosses project boundaries and reads private
sessions of unrelated projects.

- **Claude Code.** The transcript is
  `~/.claude/projects/<slug>/${CLAUDE_SESSION_ID}.jsonl`. Its subagent
  transcripts sit in `<slug>/${CLAUDE_SESSION_ID}/subagents/`.
- **Codex, or when the session id is unknown.** List the newest transcripts
  of this project with the [recall](../recall/SKILL.md) skill's script,
  resolved from this skill's directory:

  ```bash
  python3 ../recall/scripts/transcripts.py --days 1 --subagents | head -10
  ```

  Open the first user message of each candidate and take the file that holds
  this session's opening prompt.

If none matches, pass a tight digest of the session instead.

## 2. Start three reviewers in parallel

Start the three reviewers in one message, as general-purpose subagents that
can run tools. Reviewers need tool and MCP access to look up the tickets,
chat threads, and traces the transcript references. They do not edit files.

| Lens | Claude Code model | Codex reasoning effort | Prompt template |
|---|---|---|---|
| Judgment | `opus` | high | [judgment-reviewer](references/judgment-reviewer.md) |
| Tooling | `sonnet` | medium | [tooling-reviewer](references/tooling-reviewer.md) |
| Divergent | `opus` | high | [divergent-reviewer](references/divergent-reviewer.md) |

Pass each template verbatim, with the transcript path or the digest
substituted where marked. Each reviewer returns its findings in its final
report.

## 3. Synthesize

Start one more subagent on `opus` (Codex: high reasoning effort) with
[synthesizer](references/synthesizer.md) verbatim and each reviewer's full
output inlined where marked. It spot-checks citations with the same tools and
returns an Accepted, Rejected, and Backlog list.

## 4. Structural enforcement check

Move to Backlog any Accepted item that a lint rule, script, type, metadata
flag, or runtime check would enforce more reliably than prose. The
encode-lessons-in-structure principle explains why. The
[correct](../correct/SKILL.md) skill applies those fixes.

## 5. Apply

Present the synthesizer's full Accepted, Rejected, and Backlog output. Wait
for explicit approval before you apply any Accepted edit. The user picks the
subset and may redirect routings. Skill changes affect every future agent
that uses the skill. Do not apply them on your own.

Offer to file each Backlog item to the team's tracker, or run the `correct`
skill on it when the user approves. Only the Accepted list waits for
approval; the Backlog list is an offer.

Never edit a skill in a plugin cache, such as `~/.claude/plugins/cache/` or
`~/.codex/plugins/cache/`. A plugin update overwrites it. Before approval,
show the destination: `.claude/skills/<skill>/` or `~/.claude/skills/<skill>/`
(Codex: `.agents/skills/<skill>/` or `~/.agents/skills/<skill>/`). After
approval, copy the skill folder there and edit the copy.

Follow each approved row's Routing exactly:

- Trivial edit to an existing skill (a one-line bullet, a tightened sentence,
  a stale fact corrected): make it directly.
- Substantive edit to an existing skill (a new section, a new pattern table,
  more than about 10 lines): follow the
  [writing-for-agents](../writing-for-agents/SKILL.md) skill.
- `tune description: <skill path>` (the skill exists but did not trigger when
  it should have): follow `writing-for-agents` for the description.
- `new skill: <kebab-name>`: create it with `writing-for-agents`. Do not
  invent the shape ad hoc.
- A repeated agent mistake, or a Backlog item the user approves: run the
  `correct` skill, which fixes the mistake's class at the highest level that
  works.

Run the repository's skill and plugin checks on every touched skill before
you declare done.

## 6. Summarize for the user

Give a short list, with no preamble:

- Edits applied: `<skill path>`. One line each on what changed.
- New skills created: `<skill path>`. One line each (rare).
- Structural fixes or Backlog items filed: `<title>`. One line each.
- Dropped: one line per rejected finding, with the synthesizer's reason.
