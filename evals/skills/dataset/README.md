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
| `files` | The fixture repository: `{"<path in the workspace>": "../fixtures/<fixture>/<path>"}`. All paths of one sample share one fixture, and the loader requires them to list exactly that fixture's files. |
| `metadata` | Every other case field, with the same name and value. The skill under test is `target_skill`, because `target` is taken. |

Labels live in `metadata`. Scorers live in code (`../skill_eval.py`): the loader there
turns each sample back into the case dict that the scorers use and validates the corpus.
