# Prose rules

These rules apply to every prose surface: docs, skills, PR bodies, commit
messages, handoffs, plans, code comments, and replies. Edit text to remove AI
patterns. Scan for the patterns below, then rewrite. Preserve the meaning and
match the intended tone. Code, quoted text, and identifiers stay as they are.

## AI patterns to detect and fix

Rule numbers are stable ids that other skills cite. A removed rule leaves a
gap.

3. No trailing "-ing" phrases that add no fact ("highlighting...",
   "ensuring...").
5. No vague attributions ("experts believe"). Name the source or delete.
7. No AI vocabulary: additionally, crucial, delve, enhance, foster, landscape,
   pivotal, showcase, testament, underscore, vibrant.
8. Say "is" or "has", not "serves as", "stands as", "boasts", "features".
9. No "not just X, but Y". State the point.
10. Do not force ideas into threes.
11. One name per thing. Repeat it.
12. No "from X to Y" unless X and Y sit on a real scale.
13. No em dashes, en dashes, or hyphens used as dashes. Use a period or a
    comma. Parentheses are fine when the text inside is a full unit.
14. A colon goes before a list or an example, never mid-sentence as a
    connector.
15. Do not bold every proper noun or acronym.
16. No bold label and colon that restates its line ("**Performance:**
    Performance improved..."). A bold lead-in that ends in a period and adds
    new detail is fine.
17. Sentence case headings.
18. No decorative emojis.
19. Straight quotes.
20. No chatbot phrases ("I hope this helps!", "Let me know if...").
22. No praise or agreement openers. Respond directly.
23. Cut filler. "In order to" becomes "to". Delete "it is important to note
    that".
24. One hedge at most: "may".
25. No generic conclusions. State specific plans or facts.
26. No abstract metaphor nouns: substrate, wedge, vector, nexus, primitive,
    harness, surface, scaffolding, paradigm, ratchet, north star, flywheel.
    Use the concrete word.
27. Say what it does, not how it feels. Name the mechanism or the number. Cut a
    sentence that could appear unchanged in another project's docs.
28. One idea per sentence. Split a sentence that the reader has to reread.
29. Active voice. Name the actor unless it is unknown or does not matter.
30. Cut adverbs or use a stronger verb. Give the number.
31. Use the plain word: "use", not "utilize" or "leverage".
32. No metaphor, aphorism, personified code, or figurative verb where a literal
    phrase exists.
33. Write whole sentences with their articles and verbs. Spell out arrows and
    abbreviations.

## Vary the rhythm

- Mix sentence lengths. Split a sentence that carries two thoughts. Keep a
  long sentence that carries one.
- Have a view in explanation. Keep reference dry.
- Be specific. Write "a column rename fails the build", not "schema changes
  can cause issues".

## Make statements load one at a time (STE rules)

- One instruction per sentence. One thought per sentence everywhere else.
- Split an instruction longer than about 20 words. Split other sentences
  longer than about 25 words.
- Put the warning or condition before the step it guards.
- Keep "the" and "a".
- Give each word one meaning, and pick one word per action.
- Write procedures as direct commands, never as narration and never in the
  passive.
- Avoid "-ing" words where you can.

## Replies and agent-facing text (ASD-STE100)

Write replies to the user and text that agents read (skills, `AGENTS.md`,
`CLAUDE.md`, briefs, handoffs, plans) in ASD-STE100 Simplified Technical
English. The STE rules above apply, plus these:

- Use the simple, common verb ("use", "start", "stop", "show", "find"). Avoid
  phrasal verbs when one verb does the job.
- Write a sequence as a numbered list, one action per item.
- Lead with the answer, then the evidence.
- Keep the project's own terms, even when STE would pick another word.

## Leave no sentence open to two readings (Global English)

- Keep words like "only" and "not" next to the word they change.
- Break up long noun strings.
- Make every "it", "they", and "this" point at one obvious thing. Never use
  "this" or "which" to point at a whole clause.
- Keep every verb, and keep the small words that show structure, such as
  "that".
- Repeat the article in a series when it prevents a misread. Say which parts
  "and" or "or" joins.
- Use periods, not semicolons or long dashes. No slashes, and no "(s)". Make
  text in parentheses a full grammatical unit.
- Call each thing by one name, everywhere.
- Skip idioms, colloquialisms, Latin abbreviations, and metaphors.
