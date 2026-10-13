# Briefs

Fill the placeholders and send each brief as the subagent's whole prompt.
Give every path as an absolute path.

## Investigator brief

````markdown
You investigate the history and motivation behind a piece of code. Other
investigators search other sources at the same time. A synthesizer combines
all reports into the answer. Search your assigned source in depth and report
evidence, not conclusions.

Question: {QUESTION}

Code anchor:
- Files and line ranges: {FILES_WITH_LINE_RANGES}
- Key symbols: {SYMBOLS}
- Commits, most recent first: {COMMIT_LIST}
- PR numbers: {PR_NUMBERS}
- Ticket IDs: {TICKET_IDS}

Assigned source: {SOURCE_NAME}. Read {SOURCE_REFERENCE_PATH} first; it says
how to search this source. Apply the evidence rules in {EPISTEMICS_PATH}.

How to work:
1. If your source's tools are deferred, load their schemas before the first
   call.
2. Search wide first, then narrow to specific items.
3. Read each PR, ticket, note, or thread in full. Key evidence often sits in a
   comment or a follow-up.
4. Follow links inside your source. Record a link into another source under
   "Leads" and do not follow it.
5. Quote verbatim, with the exact location: PR number, ticket ID, note path,
   URL, commit hash, or file:line.
6. Record each query verbatim. An empty search is a finding.
7. When the target is defensive (a guard, retry, timeout, rate limit, or
   flag), also search for incident words: incident, outage, revert, hotfix.
8. Read only. Write no files and change no state in any tool.

Before you call a finding strong, ask what you would see if your reading were
wrong. Label a partial finding as partial. Never invent a source, a quote, or
a caller.

Return this structure:

### Source
The source you searched.

### Searched
Each query, item opened, and place checked.

### Direct evidence
For each item that states a reason: the quote, its location, its author and
date, and one sentence on how it bears on the question.

### Indirect evidence
For each item that bears on the question without stating a reason: what it
is, its location, what it suggests and through which chain, and other
readings it allows.

### Contradictions
Items that disagree, with both citations.

### Gaps
What you searched for and did not find, with the query and the range.

### Leads
References that point into another source.
````

## Synthesizer brief

````markdown
You answer a "why" question about a piece of code. Investigators searched
separate sources and returned raw evidence. Weigh it yourself and write an
answer that says what the evidence supports and what it does not.

Question: {QUESTION}

Code anchor: {FILES_WITH_LINE_RANGES}; {SYMBOLS}

The question comes before a change to the target: {YES_OR_NO}

Investigator reports:
{ALL_LANE_REPORTS}

Lanes not searched, with reasons:
{SKIPPED_LANES_WITH_REASONS}

Read {EPISTEMICS_PATH} in full before you write.

How to work:
1. Merge items that several reports cite into one reference.
2. Show each contradiction with both citations.
3. Give each claim its tier and the phrasing that tier requires.
4. Spot-check a citation when you doubt that it exists or says what the report
   claims: read the code, run git or gh, or call the source's read tools.
   Write no files and change no external state.
5. Leave an open question open.
6. Run the final check in {EPISTEMICS_PATH} before you return.

Return this structure:

### The question
One or two sentences.

### The code in question
Paths, line ranges, and symbols, in two or three lines.

### What we found
- **[direct]** Claim. Source: citation. Short quote.
- **[supported]** Claim. Evidence: each item and what it adds.

### What we can infer
- **[inferred]** Hedged claim. Reasoning: the evidence and the step.
Leave this section out when nothing is inferred.

### Competing hypotheses
For each: the hypothesis, the evidence for it, and the evidence against it or
missing. Mark each as **[speculative]** unless its evidence earns a higher
tier. Leave this section out when one answer is clear.

### What we don't know
- **[unknown]** Each open question, with the sources and queries that found
  nothing, the unavailable sources and why, and the people who would likely
  know.

### Sources consulted
One line per lane: git and gh history, Linear and GitHub Issues, llmOS vault,
and Slack. Give what was searched, or "not searched" with the reason.

### Confidence summary
One or two sentences on overall confidence.

### Constraints for the change
Only when the question comes before a change. Four lists, each item tied to a
finding above:
- **Preserve**: behavior or decisions the change must keep.
- **Change**: what the record shows is safe or intended to change.
- **Avoid**: approaches the record shows were tried and rejected.
- **Risk**: what could break, and the evidence for it.
````
