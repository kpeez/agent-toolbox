---
pretty_name: Skill activation evals
language:
  - en
tags:
  - synthetic
  - agent-evals
  - inspect
configs:
  - config_name: default
    data_files:
      - split: dev
        path: dev.jsonl
---

# Skill activation evals

Synthetic scenarios that test whether an agent loads the right skill. Authored
for this repository. They hold no real user data. There are 136 samples; the
20 with `metadata.split` set to `holdout_candidate` are disclosed development
material, not a sealed holdout, so they stay in `dev.jsonl`.

Each line of `dev.jsonl` is one [Inspect `Sample`](https://inspect.aisi.org.uk/datasets.html).

| Sample field | Content |
| --- | --- |
| `id` | Case ID. |
| `input` | The conversation as `{"role", "content"}` messages. The last message is from the user. |
| `target` | The expected route facet. Present only on cases that expect a route. |
| `files` | The fixture repository: `{"<path in the workspace>": "../fixtures/<fixture>/<path>"}`. All paths of one sample share one fixture, and the loader requires them to list exactly that fixture's files. The loader reads `<fixture>` from the `fixtures/` folder beside the `.jsonl` file, for this corpus and for the sealed holdout. Inspect's own loader resolves these paths from the `.jsonl` file's folder, one level up, so it does not find them. |
| `metadata` | Every other case field, with the same name and value. The skill under test is `target_skill`, because `target` is taken. |

## Sealed holdout

A sealed holdout of 32 samples lives outside this public repository, so that
agents that edit the skills cannot read it. A separate author wrote it from the
routers and playbooks alone, without seeing `dev.jsonl`. Its folder holds
`holdout.jsonl` (same `Sample` shape, `metadata.split` set to `holdout`), its
own `fixtures/`, the author's brief and notes (`AUTHOR-BRIEF.md`, `AUTHORING.md`),
the plugin commit it was written against (`plugins-source-sha.txt`), and
`MANIFEST.sha256`, which lists the SHA-256 of every other file.
`holdout.sha256` here pins that manifest. To check a copy, run
`shasum -a 256 -c holdout.sha256` in the holdout folder, then
`shasum -a 256 -c MANIFEST.sha256`. Score it only to measure a change, never
while you edit a skill or this corpus.

Labels live in `metadata`. Scorers live in code (`../skill_eval.py`): the loader there
turns each sample back into the case dict that the scorers use and validates the corpus.
