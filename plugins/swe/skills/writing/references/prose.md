# Prose rules

These rules apply to every prose surface: docs, skills, PR bodies, commit
messages, handoffs, plans, code comments, and replies. Rule numbers in the AI
patterns are stable ids that other skills cite. A removed rule leaves a gap.
Code, quoted text, and identifiers stay as they are.

## AI patterns to detect and fix

Rule numbers are stable ids that other skills cite. A removed rule leaves a
gap.

### Content

3. **Superficial -ing phrases.** "highlighting...", "ensuring...",
   "reflecting...", "showcasing...", "fostering...". Delete them, or expand
   them with real sources.
5. **Vague attributions.** "Experts believe", "Industry reports suggest",
   "Some critics argue". Name the source or delete.

### Language

7. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance,
   fostering, garner, interplay, intricate, landscape (abstract), pivotal,
   showcase, tapestry (abstract), testament, underscore, vibrant. Replace them
   with plain words.
8. **Fancy ways to say "is".** "serves as", "stands as", "boasts",
   "features". Say "is" or "has".
9. **"Not just X, but Y."** State the point directly.
10. **Rule of three.** Use the natural count of items, not a forced group of
    three.
11. **Synonym cycling.** Protagonist, main character, central figure, and hero
    in one paragraph. Pick one name for a thing and repeat it.
12. **False ranges.** "from X to Y" where X and Y are not on a meaningful
    scale. List the topics directly.

### Style

13. **Long dash overuse.** Use no em dashes and no en dashes, and no hyphen
    used as a dash. If a thought needs separation, end the sentence or use a
    comma. Parentheses are fine when the text inside is a full unit.
14. **Colon overuse.** A colon is fine before a list or an example, not as a
    mid-sentence connector. "If you're coming from traditional automation:
    instead of registering event handlers, you describe conditions" gains
    nothing from the colon. Rewrite so the point stands on its own, without
    comparison framing: "Describing when the scheduler should fire works best
    as plain English." The meaning is the same, without the crutch.
15. **Boldface overuse.** Do not bold every proper noun or acronym.
16. **Inline-header lists.** The tell is a bold label and colon that restates
    the line: "**Performance:** Performance improved...". Convert those to
    prose. A bold lead-in that ends in a period, names the item, and is
    followed by new detail ("**Schema in TypeScript.** Tables live in one
    file.") is fine.
17. **Title case headings.** Use sentence case.
18. **Decorative emojis.** Remove them from headings and bullets.
19. **Curly quotes.** Use straight quotes.

### Communication artifacts

20. **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of
    course!", "Certainly!", "Found the smoking gun!" Remove them.
22. **Sycophantic tone.** "Great question! You're absolutely right!" Respond
    directly.

### Filler

23. **Filler phrases.** "In order to" becomes "to". "Due to the fact that"
    becomes "because". Delete "It is important to note that".
24. **Excessive hedging.** "could potentially possibly be argued that it
    might" becomes "may". Use one hedge at most.
25. **Generic conclusions.** "The future looks bright." End on a specific
    plan or fact.

### Jargon

26. **Abstract metaphor nouns.** Substrate (base), wedge, wedge in (add),
    vector (way, method), locus, vantage, nexus, primitive as a noun, harness
    as a metaphor, surface as in "API surface", bedrock, scaffolding as a
    metaphor, modality, paradigm, gold-plating (more than the job needs),
    ratchet as a metaphor (the real name of the mechanism, or a limit that
    only tightens), evacuate for moving code (move out), endgame (the last
    phase), north star, flywheel. These read as technical, but a plainer
    concrete word usually exists. Pick the concrete word.

### Plain speech

27. **Say what it does, not how it feels.** "the database stays close at
    hand", "SQL you can read", and "types that follow your schema" name a
    feeling. The fix names the mechanism or a number: "`.toSQL()` returns the
    exact string sent to the database", "a column rename fails the build". Ask
    what the sentence tells the reader to do or know, then write that. If you
    cannot restate it as a concrete instruction, fact, or number, cut it. If
    the sentence could appear unchanged in another project's docs, it says
    nothing about this one. Cut it.
28. **Shorten or split dense sentences.** If the reader has to backtrack to
    parse a sentence, break it in two or drop clauses. One idea per sentence.
29. **Active voice.** Catch "is/are/was/were + past participle" and name the
    actor: "queries are validated" becomes "the compiler validates queries",
    and "the file is parsed by the loader" becomes "the loader parses the
    file". Use passive only when the actor is unknown or does not matter.
30. **Cut adverbs, or use a stronger verb.** "runs quickly" becomes "is fast"
    or the number, and "significantly improves" becomes the measured change.
    An adverb that props up a weak verb means the verb is wrong.
31. **Prefer the plain word.** "utilize" and "leverage" become "use",
    "facilitate" becomes "help", "numerous" becomes "many", and "in the event
    that" becomes "if".
32. **Mannered prose.** Metaphor or flourish where a literal phrase exists:
    aphorisms ("wire it or delete it"), rhetorical fragments for effect,
    personified code ("the plan holds it"), figurative verbs ("rides along",
    "stands on"), and stock framing phrases. "A dial worth turning" becomes "a
    parameter worth varying". Say what you mean. Rule 26 covers the metaphor
    nouns.
33. **Over-compression.** Dropped articles, verbless fragments, symbol-speak,
    and abbreviations make the reader decode instead of read. "Parser rejects
    bad date, exit 2, no write" becomes "The parser rejects a bad date, exits
    with code 2, and writes nothing." Write whole sentences with their
    articles and verbs, and spell out arrows, symbols, and abbreviations.

## Vary the rhythm

A doc can obey every layer and still read as if a machine wrote it: every
sentence clipped short, no view anywhere, nothing specific.

- Mix sentence lengths on purpose. Short sentences land a point. Longer ones
  carry a fact with its condition or consequence.
- Split the sentence that carries two thoughts. Keep the long sentence that
  carries one.
- Have a view where the mode allows it. An explanation weighs trade-offs, so
  say what you make of them instead of listing pros and cons. A reference
  stays dry.
- Be specific. Write "a column rename fails the build", not "schema changes
  can cause issues".

## Make statements load one at a time (STE rules)

- Write one instruction per sentence. Write one thought per sentence
  everywhere else.
- Split an instruction longer than about 20 words. Split other sentences
  longer than about 25 words.
- Put the warning or condition before the step it guards: "If hot oil touches
  your skin, injuries can occur."
- Keep "the" and "a". "Remove backup file" has two readings. "Remove the
  backup file" has one.
- Give each word one meaning and one job, then keep it. If "check" means
  inspect, do not also use it to mean restrain.
- Pick one word per action and keep it: "start", not "start" here and
  "initiate" there.
- Write procedures as direct commands, never as narration and never in the
  passive: "Install the component", not "the component must be installed".
- Avoid "-ing" words where you can.

## Replies and agent-facing text (ASD-STE100)

Write replies to the user and text that agents read (skills, `AGENTS.md`,
`CLAUDE.md`, briefs, handoffs, plans) in ASD-STE100 Simplified Technical
English. The STE rules above apply, plus these:

- Keep an instruction to 20 words or fewer and a description to 25 or fewer.
- Use the simple, common verb: "use", "start", "stop", "show", "find". Do not
  use phrasal verbs ("set up", "carry out") when one verb does the job.
- Use the active voice. Use the past participle only as an adjective.
- Do not use "-ing" forms as nouns or adjectives.
- Write a sequence as a numbered list, one action per item.
- Lead with the answer, then the evidence. Cut words that do not change what
  the reader does next.
- Keep the project's own terms, even when STE would pick another word.
- Code, identifiers, commands, paths, and quoted text stay as they are.

## Leave no sentence open to two readings (Global English)

- Keep words like "only" and "not" next to the word they change. "Only fails
  on growth" and "fails only on growth" say different things.
- Break up long noun strings. "The proto import budget check script" becomes
  "the script that checks the proto-import budget".
- Make every "it", "they", and "this" point at one obvious thing. Repeat the
  noun when in doubt. Never use "this" or "which" to point at a whole clause.
- Keep every verb. "Phase 1 moves the converters and Phase 2 the runtime"
  leaves Phase 2 without one. Give it one.
- Keep the small words that show structure, such as "that" in "Ensure that
  the switch is off". Never trade clarity for word count.
- Repeat the article in a series when it prevents a misread: "the client and
  the host", not "the client and host", when they are two things.
- Say which parts "and" or "or" joins when a sentence can group two ways.
  "Both...and", "either...or", and "if...then" remove the doubt at no cost.
- Use periods, not semicolons. Replace a long dash with a new sentence.
- Make text in parentheses a full grammatical unit. Never form plurals with
  "(s)".
- Write "a, b, or both" instead of "a/b" or "and/or".
- Call each thing by one name, everywhere. A doc that says "the gate", "the
  ratchet", and "the budget check" for one thing teaches three things. Leave
  the names of unchanged things as they are.
- Skip idioms, colloquialisms, Latin abbreviations, and metaphors.

## Done

Every rule above is checked against the whole text, and each hit is
rewritten or deliberately kept.
