# Source: project docs

Project docs hold decision records (ADRs), research notes, and closeout
notes. They often record the reason for a design before the code lands. They
live in `.agents/docs/` unless the project or user names another place; that
folder can be a symlink.

## Read only

Use `Read`, `Grep`, and `Glob`. Write nothing.

## Search

1. Resolve the docs folder. Follow the symlink when `.agents/docs` is one.
2. List the decision records, usually under `adrs/`, and open each relevant
   one.
3. Search the folder for the feature name, a key symbol, the PR number, or
   the decision words.
4. Search for notes that link to a relevant note, such as a later decision or
   a closeout note.

## Read with care

- Report the status of every decision record you cite, and what supersedes
  it. Follow the chain to the record that is in force, and say which parts
  of the old record it keeps.
- Report each note's dates and authors when it has them. Agents write many
  notes; an agent-written note records what the session decided, not
  necessarily the user's own words.
- A plan can describe intent that the code later changed. Compare it with the
  merged code.
