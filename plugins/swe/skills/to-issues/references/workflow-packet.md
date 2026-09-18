# Workflow packet and mapping

The tracked workflow builds a runtime packet from the approved spec and the
current task judgment. Building the packet is part of `/to-issues`; there is no
separate manual packet command to keep in sync. `schema_version` 1 is current;
confirm exact names with `--help`.

Read this reference only when the invocation publishes or resumes tracked work.

## Packet

A packet describes the approved revision once so later operations do not reread
arbitrary project text:

- `spec`: stable UUID4 `spec_id`, title, the approved markdown, and metadata such as
  `tracker`, `tracker_container`, `tracker_document`, and the approved semantic
  digest and revision. Preserve meaningful legacy metadata and mappings;
  bookkeeping stays excluded from the digest. Do not rewrite the source.
- `context`: ordered references the agent has judged relevant. Each entry names
  its documentation root separately from the code repository, host, or artifact
  (separate `documentation_roots` and `code_roots` config), and carries a relative path or a usable approved link plus role, relevance,
  revision, hash, knowledge date, standing, access, and whether it is essential.
  Curate this index; the runtime validates declared paths only and never scans a
  whole vault. `relevance` is a concise explanation of why this task needs the
  reference. `role` and `access` use the runtime's defined vocabulary.
- `project`: name, summary, and closure condition.
- `tasks`: each task's stable UUID4 id, outcome, title, acceptance criteria, kind (`code`,
  `research`, or `operation`), context ids, dependencies, repository, base
  branch, and completion conditions such as required pull requests and checks.
  Operational work declares its review expectation plainly; it does not invent
  a PR requirement.

## Mapping

The mapping binds stable identifiers for the project, spec, context, task, and
dependency relationships so later runs reuse them instead of recreating work. If
a recorded project is unavailable or archived, stop and report it rather than
creating a duplicate or an empty backlog. Writes use a durable UUID intent
before network, inspect the exact remote identity before retry, and keep
revision documents and comments immutable to protect human edits; read back
receipts after apply.

When the tracker cannot take a conditional write, append the new approved
revision to the content mirror. Preserve human edits and report the sync
conflict instead of overwriting them.
