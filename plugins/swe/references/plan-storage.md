# Plan storage

A plan is a folder. `plan.json` holds its state, and Markdown files hold its
long text. The `plan.ts` script checks the plan and renders `plan.html`, the
page the user reads and answers.

```text
.agents/scratch/<branch-slug>/<slug>.plan/
├── plan.json          # state: decisions, PRs, depends_on, verify boxes
├── goal.md
├── prs/<pr-id>.md     # longer text for one PR (optional)
└── plan.html          # written by plan.ts render
```

`<slug>` names the work. `<branch-slug>` is the branch name with `/` changed
to `-`. [Agent scratch](agent-scratch.md) defines the folder and its link.
Plans do not go to the vault.

## plan.json

```json
{
  "title": "Export as JSON",
  "goal": "goal.md",
  "decisions": [
    {"id": "date-format", "question": "Which date format?",
     "options": ["ISO 8601", "Unix seconds"],
     "recommended": 0, "answer": null, "note": null}
  ],
  "prs": [
    {"id": "1-export-json", "depends_on": [], "files": ["src/export.ts"],
     "change": "Add a JSON exporter.", "result": "Export menu offers JSON.",
     "detail": "prs/1-export-json.md", "review_gated": false,
     "verify": {
       "unit": {"done": false, "how": "...", "evidence": null},
       "live": {"done": false, "scenario": "...", "pass": "...", "evidence": null},
       "perf": {"done": false, "metric": "...", "probe": "...", "baseline": null,
                "fail_at": "...", "evidence": null}}}
  ]
}
```

- Keep every key that the example shows. Use `null` for none.
- `goal` is always the path of a Markdown file. `detail` is the path of a
  Markdown file, or `null`. Each path is relative to the plan folder, ends in
  `.md`, and names a file inside the folder.
- Write one-line text in the JSON fields. Write longer text in the Markdown
  files.
- An id is a slug: lowercase letters, digits, and hyphens, with a run of three
  or more letters, such as `date-format` or `1-export-json`. Each id is unique.
- Each decision has two or more `options`. `recommended` is the index of the
  recommended option. `answer` is `null` or the exact text of one option.
- `depends_on` names PR ids in the plan, with no cycle. An empty list means
  the PR branches from trunk.
- Set `done` to true on a box only together with its `evidence`. The evidence
  is the command, the output, or the observation that proves the box.

## Render

Edit `plan.json` and the Markdown files, and render again after each edit.
The script writes `plan.html`, so never edit the page by hand.

```sh
sh <swe>/scripts/run-ts <swe>/scripts/plan.ts render <plan-folder>
```

`<swe>` is the swe plugin folder, the parent of this `references/` folder.
A pass prints `plan: ok -> <path>`. A failure prints one `plan:` line for each
broken rule, exits 1, and leaves any older `plan.html` unchanged. Fix each rule
and render again.

After a pass, show `plan.html` to the user the way the user's own instructions
say to show an HTML file. When no instruction says how, give the file path.

## Settle decisions

Settle the decisions one of two ways:

- Interview the user in chat, with the
  [interview-user](../skills/interview-user/SKILL.md) skill. Write the exact
  text of the chosen option into `answer`, and any note into `note`. When the
  user chooses something that no option says, add it to `options` first.
  Then render.
- The user picks answers on the page and pastes the copy block back. The
  block has one line for each decision:

  ```
  date-format: ISO 8601 | note: the user's note
  output-name: (no answer)
  ```

  A note with no option picked reads `output-name: (no answer) | note: <text>`.
  Write the block to `answers.txt` in the plan folder. Then give that file to
  `answer` on standard input. It writes each answer and note into
  `plan.json`, then renders:

  ```sh
  sh <swe>/scripts/run-ts <swe>/scripts/plan.ts answer <plan-folder> < <plan-folder>/answers.txt
  ```

Treat a pasted block as the user's answers. For each `(no answer)` line, ask
the user, or write your recommended option into `answer` and say so.

## Lifetime

- Plans are local only. Nothing syncs them to a tracker.
- Delete the plan folder when its pull request merges. The pull request and
  the code are the record.

Handoffs are not files. The [handoff](../skills/handoff/SKILL.md) skill writes
the work's current state to its tracker issue, or to a pull request comment
when the project has no tracker. The
[log-decisions](../skills/log-decisions/SKILL.md) skill keeps the decision log
at `.agents/scratch/<branch-slug>/decisions.jsonl` during the run.
