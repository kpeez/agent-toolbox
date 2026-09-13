# Task format defaults

Read this only when the selected tracker has no established issue-body or label
convention. Adapt it to the tracker's native fields and relationships.

## Optional triage labels

| Label | Meaning |
| --- | --- |
| `needs-triage` | Needs evaluation before work |
| `needs-info` | Waiting for information |
| `ready-for-agent` | Fully specified for an agent |
| `ready-for-human` | Needs a human decision or implementation |
| `wontfix` | Will not be actioned |

## Issue body

```md
## Outcome

<The behavior, artifact, or decision this task must produce.>

## Context and starting points

- <Relevant requirement, path, component, or prior decision.>

## Acceptance criteria

- [ ] <Observable, checkable criterion and acceptable evidence.>

## Scope

- In: <owned work>
- Out: <adjacent work>

## Blocked by

- <Native dependency reference, or none>

## Authority and escalation

<External-action limits and consequential blocker route, when applicable.>
```
