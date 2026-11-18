# Pull requests

Read from the forge on 2026-11-16 at 08:30 UTC.

## 57: Round discounted lines half up

- State: merged on 2026-11-13 at 09:52 by tally-agent (squash).
- Checks at the merged head: tests (python 3.12) passed, tests (python 3.9) passed, lint passed.
- Verifier comment: PASS. "Exported the sample invoices before and after. A line of 2.345 now reads 2.35, before 2.34. The other 41 lines are unchanged."

## 55: Pin csv-schema to 2.4

- Author: jonas-ferreira. Not part of the queue.
- State: merged on 2026-11-14 at 11:05 by jonas-ferreira (squash).

## 58: Add a currency column to the CSV export

- State: open, ready for review, head f04c6d1. Mergeable.
- Checks at f04c6d1: tests (python 3.12) passed, tests (python 3.9) passed, lint passed.
- Verifier comment: PASS+NOTES. "The column is correct for every sample invoice. Note: it sits between customer and total, and the ledger importer reads total as the third column, so a merge breaks the import. See decisions.md, 2026-11-14 18:40."
- Labels: hold-for-operator.

## 59: Document the --out flag in the README

- State: merged on 2026-11-15 at 16:40 by tally-agent (squash).
- Checks at the merged head: tests (python 3.12) passed, tests (python 3.9) passed, lint passed, links passed.
- Verifier comments: FAIL at 2d1a7c0 ("the example uses --output, which the command rejects"), then PASS at 6e0f3b8 after the fix.
