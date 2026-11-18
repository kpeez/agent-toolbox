# Decision log: invoice export queue

2026-11-12 14:10. Queue of three independent PRs: rounding (57), currency column (58), README for --out (59). One owner per PR, off main, each merges when verified.

2026-11-13 09:52. 57 merged after a PASS verdict and green checks.

2026-11-14 11:30. 55 by jonas-ferreira merged to main. It only pins csv-schema. Rebased 58 onto it; checks stayed green.

2026-11-14 18:40. 58 holds at merge-ready. The ledger importer, in another repository, reads the CSV columns by position. A currency column between customer and total moves total to the fourth column. Two ways out: put currency last, which needs no importer change, or keep it beside total and change the importer, which is outside the queue's grant. This is the operator's call, so 58 waits.

2026-11-15 10:05. 59 verifier FAIL: the README example used --output. The owner fixed it to --out.

2026-11-15 16:40. 59 merged after a PASS verdict and green checks.

2026-11-15 17:00. Nothing left to build. The hourly check stays armed until 58 is decided.
