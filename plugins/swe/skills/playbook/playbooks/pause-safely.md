# pause-safely

Applies when: the user explicitly asks to pause in-flight work, is going offline, the host is about to restart, or context compaction is imminent.

You own a clean stop. Leave a checkpoint a cold-start agent can resume from.

This playbook runs only on an explicit pause. On "keep going", "going to bed, keep going", or "don't stop", do not pause; that is run-autonomously. The pause request authorizes the local `wip:` commit below. It does not authorize a push or a PR.

1-stop-at-safe-boundary: Finish the current atomic step or back out of it. Start nothing new, and stop any nested subagents.
2-take-no-irreversible-action: Take no irreversible action to pause. Open no PR, and push nothing unless a PR was already out.
3-commit-wip: Commit your uncommitted edits on the current branch as one clear `wip:` commit, so nothing is lost. Leave unrelated changes untouched. When the tree is broken, say so in one line of the commit body. (ship-pr)
4-write-handoff: Write the resume note to the work's handoff file. Capture intent, what you were doing, progress and what is verified, current state, next steps, key files, and gotchas. When a decision log exists, point at it instead of copying it. (handoff, log-decisions)

Reply: where you are in the loop, what is on disk versus still only in context (paths, no diff dumps), the commits you made and whether the tree is clean, the handoff path, and the first action on resume. This is a pause, not a final report.
