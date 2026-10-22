# Tech tree format

## `tech-tree.json`

One file per course. JSON, so the script needs only the Python standard library.

```json
{
  "course": "linear-equations",
  "topics": [
    {
      "id": "integer-arithmetic",
      "title": "Arithmetic with signed integers",
      "goal": "Learner computes with negative integers.",
      "check": "Mixed signed-integer items such as -7 - (-3), without a calculator.",
      "minutes": 20,
      "requires": {},
      "kps": [
        {"title": "Add and subtract signed integers", "key": []},
        {"title": "Multiply and divide signed integers", "key": []}
      ]
    },
    {
      "id": "one-step-equations",
      "title": "One-step equations",
      "goal": "Learner solves x + a = b or ax = b.",
      "check": "Equations with negative coefficients; verify each answer by substitution.",
      "minutes": 20,
      "requires": {"integer-arithmetic": "each step adds, subtracts, or divides signed numbers"},
      "kps": [
        {"title": "Add or subtract to isolate x", "key": ["integer-arithmetic"]},
        {"title": "Divide to isolate x", "key": ["integer-arithmetic"]}
      ],
      "encompasses": {"integer-arithmetic": 0.5}
    }
  ]
}
```

| Field | Rule |
| --- | --- |
| `id` | Kebab-case, unique, stable. Progress uses it. |
| `title` | Short name for the tree view. |
| `goal` | One skill: "Learner can ...". |
| `check` | The kind of items that show the goal. Practice and review items come from it. The skill's pass rule decides a pass. |
| `minutes` | Optional. 10-30. |
| `requires` | Map of prerequisite id to the reason the edge exists. All are needed. |
| `kps` | 1-4 knowledge points, easy to hard. `key` lists the earlier topics each step uses directly. |
| `encompasses` | Optional. Map of ancestor id to 0.5 (partly practiced) or 1.0 (fully practiced). |

`validate` fails on: a field of the wrong type; a bad or duplicate id; an unknown id in `requires`; an edge without a reason; an empty title, goal, or check; a cycle; a KP without a title; a `key` or `encompasses` target that is not an ancestor; a weight other than 0.5 or 1.0.

`validate` warns on: more than 4 direct prerequisites; no KPs or more than 4; more than 30 minutes; a goal that joins two skills with "and"; a redundant edge that another prerequisite already implies.

## `progress.json`

The script writes it beside the graph. Do not edit it by hand.

```json
{
  "topics": {
    "integer-arithmetic": {"status": "mastered", "fails": 0, "reps": 2, "due": "2026-10-25"}
  },
  "log": [
    {"date": "2026-10-22", "id": "integer-arithmetic", "kind": "lesson", "result": "pass", "helped": false}
  ],
  "reviews_since_lesson": 0
}
```

| Status | Meaning |
| --- | --- |
| `unseen` | Not taught or placed. |
| `learning` | Taught or retaught, not yet passed without help. |
| `conditional` | Placed by the diagnostic. Counts as met until a failed review or placement. |
| `mastered` | Passed without help. Has review dates. A mastered topic stays mastered when a topic below it fails; its own reviews test it. |

`reps` counts repetitions, with fractional credit from encompassing topics. `due` is the next review date. `log` keeps every result, helped or not, so a tutor can see the learner's history.

When a topic splits or its id changes, move its entry in `progress.json` to the new id, or delete it so the topic starts as `unseen`. The script warns about entries with unknown ids.
