# Inventory rollout notes

Move stock updates from daily batch files to a local event feed.
Constraints: preserve the existing spreadsheet import for one release, reconcile duplicate events,
and let operators compare old and new totals before cutover. Avoid changes to the warehouse scanner.

The request is for a handoff plan. A separate implementation session will do the work.
