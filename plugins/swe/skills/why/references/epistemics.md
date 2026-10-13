# Epistemics

Code shows what it does, not why it exists. The why lives in commits, PRs,
tickets, notes, and chat. That record is incomplete, biased, and sometimes
contradictory. These five tiers are the one confidence scale for claims about
rationale, history, and the answers to investigation questions.

## Tiers

Every claim sits in exactly one tier. The tier sets the claim's section in the
answer and its phrasing.

### direct

An author wrote down the reason. Examples: a PR body ("this fixes pagination
for users with more than 1000 items"), a ticket ("customer Acme asked for this
in their security review"), a code comment ("clamp to 100 because the upstream
API rejects larger values"), an ADR ("we chose a file store because state must
survive restarts"), or a chat message from the author.

Phrasing: plain, present tense, with the citation next to the claim. "This
exists because X (PR #123)."

### supported

Several indirect items point to one conclusion, and no single item states it.
Example: the PR title says "improve performance", the ticket has a `perf`
label, and the commits of that week all touch the same hot path.

Phrasing: firm, with each item cited. "The evidence points to X: A, B, and C."

### inferred

A reasonable reading of the context that no item states or directly supports.
It is your interpretation. Example: the PR gives no reason, but it merged on
the day of an incident thread, so it was likely a hotfix.

Phrasing: hedged, with the chain shown. "Given A and B, C seems likely because
D."

### speculative

A plausible hypothesis on thin evidence, where other explanations fit equally
well. Present it, because the user may know the answer, and mark it as a
guess. It usually sits among competing hypotheses.

Phrasing: "One possibility is X; no evidence confirms it."

### unknown

You searched and found no answer. This is a valid and important result.

Phrasing: name each source and each query. "We searched Linear for A and B,
read the 6 PRs that touched this file since 2023, and searched the repository
for the literal value. None gave a reason."

## Phrasing

- Words that claim intent or effect need a citation next to them: "because",
  "the reason is", "was designed to", "fixes", "solves", "the team decided".
  Use them only for `direct` and `supported` claims.
- For `inferred` and `speculative` claims, use hedges: "appears to", "likely",
  "suggests", "is consistent with", "one reading is", "may have been".
- Write "the evidence suggests" for your judgment. Leave out "obviously",
  "clearly", "of course", "just", "I think", and "I believe".

## Evidence rules

- Mechanics are not motivation. A diff that changes `limit = 50` to
  `limit = 100` shows the change. Look for its reason in the message, the PR,
  the ticket, or the review.
- Claim intent only where an author stated it. Code, naming, and style are
  observations about the code, not evidence of intent.
- History can be messy. A shape that makes sense today may come from reasons
  that no longer apply, or from copy and paste. Report the history the record
  shows, not a clean story built backward from the result.
- A missing record is a gap. "No one mentioned security" does not show that
  security was not a concern.
- A hypothesis in the user's question is one candidate. Test it against the
  evidence like any other, and say plainly whether the evidence supports it.
- When two items disagree, show both with their citations, and let the user
  decide. Both can be true: a ticket can give the motive and a PR the author's
  framing.
- Name each gap concretely: the question, the sources, the queries, and what
  came back. An honest "unknown" tells the user whom to ask next.

## Final check

Before the answer goes out, check every claim:

1. Each `direct` and `supported` claim has a citation: a PR number, ticket ID,
   note path, chat link, commit hash, or `file:line`. Otherwise move it to a
   lower tier.
2. Its phrasing matches its tier.
3. No claim uses code as evidence for its own intent.
4. Every contradiction you saw is in the answer.
5. "What we don't know" names specific gaps. An empty gap list is a warning:
   check the record again before you send it.
6. The tone matches the evidence. A confident answer on weak evidence is the
   failure this skill exists to prevent.
