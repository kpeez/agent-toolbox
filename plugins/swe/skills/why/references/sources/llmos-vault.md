# Source: llmOS vault

The vault holds project decision records (ADRs), plans, research notes, and
closeout notes. It often records the reason for a design before the code
lands. Use the llmos MCP tools. Paths are relative to the vault root.

## Read only

Call only `search`, `read`, `list`, `neighbors`, and `subgraph`. Never call
`daily_append_thought`, `file_inbox`, or `set_property`.

## Search

1. Find the project folder. A repository's `.agents/docs` symlink usually
   points to it, for example `projects/<repo>`. Otherwise search for the
   repository name.
2. Read the frontmatter of the project's decision records with
   `list(folder: "<project>/adrs")`. Open each relevant one with `read`.
3. Search with `search` for the feature name, a key symbol, the PR number, or
   the decision words. Add `semantic: true` when the note may use other words.
4. Use `neighbors` on a relevant note to find notes that link to it, such as a
   later decision or a closeout note.

## Read with care

- Report `status` and `superseded_by` for every decision record you cite.
  Follow `superseded_by` to the record that is in force, and say which parts
  of the old record it keeps.
- Report each note's `created`, `updated`, and `authors`. Agents write many
  notes; an agent-written note records what the session decided, not
  necessarily the user's own words.
- A plan can describe intent that the code later changed. Compare it with the
  merged code.
