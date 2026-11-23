# pause-safely

Applies when: the user explicitly asks to pause in-flight work, is going offline, the host is about to restart, or context compaction is imminent: stop the work cleanly so a new session can resume it.

You own a clean stop. Leave a checkpoint a cold-start agent can resume from.

This playbook runs only on an explicit pause. On "keep going", "going to bed, keep going", or "don't stop", do not pause; that is run-autonomously. The pause request authorizes the local `wip:` commit below. It does not authorize a push or a PR.

1-stop-at-safe-boundary: Finish the current atomic step or back out of it. Start nothing new, and stop any nested subagents.
2-take-no-irreversible-action: Take no irreversible action to pause. Open no PR, and push nothing unless a PR was already out.
3-commit-wip: Commit your uncommitted edits on the current branch as one clear `wip:` commit, so nothing is lost. Leave unrelated changes untouched. When the tree is broken, say so in one line of the commit body. (ship-pr)
4-write-handoff: Run the handoff skill to write the resume state to the work's tracker issue. Capture intent, what you were doing, progress and what is verified, current state, next steps, key files, and gotchas. The decision log's key rows go to the issue as one comment. (handoff, log-decisions)

Reply: where you are in the loop, what is on disk versus still only in context (paths, no diff dumps), the commits you made and whether the tree is clean, the issue you updated and the resume prompt, and the first action on resume. This is a pause, not a final report.
