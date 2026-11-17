#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Derive every testable workflow facet from the skill sources, and write or check the facet map.

`write` regenerates facets.json and FACETS.md. `check` exits 1 when either differs from the sources.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import NamedTuple

import skill_eval

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLUGINS = REPO / "plugins"
JSON_OUT = HERE / "facets.json"
MD_OUT = HERE / "FACETS.md"

KINDS = {
    "activation": {
        "evidence": "skill-call",
        "scorer": None,
        "scope": "root",
        "about": "The model loads a model-invocable skill when a request fits its description.",
    },
    "hook-load": {
        "evidence": "hook-delivery",
        "scorer": "recorded",
        "scope": "root",
        "about": "A session-start hook names a skill to load before a new task.",
    },
    "route": {
        "evidence": "assistant-text",
        "scorer": "invisible",
        "scope": "root",
        "about": "The router says `Playbook: <slug>` or `Route: <skill>` for a task it matches.",
    },
    "route-load": {
        "evidence": None,
        "scorer": None,
        "scope": "root",
        "about": "When the router routes to a skill, the agent loads that skill.",
    },
    "playbook-read": {
        "evidence": "full-read",
        "scorer": "recorded",
        "scope": "root",
        "about": "The agent reads the chosen playbook file in full.",
    },
    "step-load": {
        "evidence": None,
        "scorer": None,
        "scope": "delegate-allowed",
        "about": "Before a playbook step, the agent loads each name in the step's parentheses.",
    },
    "reply-load": {
        "evidence": None,
        "scorer": None,
        "scope": "delegate-allowed",
        "about": "Before the final reply, the agent loads each name in the playbook's Reply line parentheses.",
    },
    "trigger-load": {
        "evidence": None,
        "scorer": None,
        "scope": "delegate-allowed",
        "about": "When a router trigger applies, the agent loads the name the trigger gives.",
    },
    "principle-read": {
        "evidence": "full-read",
        "scorer": "recorded",
        "scope": "root",
        "about": "The agent reads a principle's SKILL.md in full before it applies the principle.",
    },
    "router-contract": {
        "evidence": None,
        "scorer": "invisible",
        "scope": "root",
        "about": "A rule of the router itself, pinned to an anchor phrase in the router file. "
        "Its scorer status is `invisible` even when a Skill call or Read proves the load, because "
        'the rule also sets an order or a context, such as "before match" or "the one it picks", '
        "that the scorer cannot see.",
    },
}
EVIDENCE = {
    "skill-call": "A Skill tool call that delivers the skill body.",
    "full-read": "A Read of the whole file at `path` (plugin-relative).",
    "skill-call-or-full-read": "A Skill call by the project skill's name, or a full Read of `path` "
    "(relative to the research repository root).",
    "agent-spawn": "A subagent start whose brief carries what the rule names.",
    "assistant-text": "Text the agent writes to the user.",
    "task-list": "Task-list tool calls: one task per step, and their state changes.",
    "final-reply-section": "A section of the final reply.",
    "hook-delivery": "The session-start hook text reaches the model, then the named skill loads.",
}
REQUIREMENTS = {
    "always": "The workflow always asks for it once its route or step is reached.",
    "conditional": 'A condition in the text decides it: a step that starts with "When " or says '
    '"Skip when" or "Skip for", every trigger, every hook, and a principle no '
    "always step names.",
    "one-of": "The step picks exactly one of the names (declared in `ONE_OF` and checked against the step).",
    "transitive": "The step runs steps of another playbook, or the whole playbook (declared in "
    "`WHOLE_RUNS`), so the names in those steps load too. `via` is the step's own load facet for "
    "that playbook. `conditional` is true when the step is conditional or every step that "
    "supplies the name is conditional.",
}
SCOPES = {
    "root": "Only the main chat satisfies it.",
    "delegate-allowed": "A load inside a subagent the step delegates to also satisfies it. "
    "The scorer records subagent loads, but no case scores them.",
}
SCORERS = {
    "scored": "A case field scores it.",
    "recorded": "The scorer records the load, but no case field scores it.",
    "invisible": "The scorer drops the event.",
}
ROUTERS = {"swe": "swe-mode", "lab": "lab-mode"}
PROJECT_SKILL_ANCHORS = {
    "lab": {"research-context": "a project skill, such as `research-context`"}
}
ONE_OF = {
    ("lab", "review-literature", "6-write-the-report"): ("research", "deep-research")
}
TRANSITIVE = {
    "lab": "When a step runs steps of another playbook, also load the names in those steps"
}
WHOLE_RUNS = {
    ("lab", "bootstrap-project", "5-codify-the-top-procedure"): "codify-procedure"
}
EXTRA_ROUTES = {
    ("swe", "figure-it-out"): "or work that no playbook fits goes to `figure-it-out`."
}
TRIGGER_IGNORE: set[tuple[str, str]] = set()
CONTRACTS = [
    (
        "go-deeper-before-match",
        "skill-call",
        {
            "swe": "Run `go-deeper` on a new task, unless it already ran for this task or its skip rule applies.",
            "lab": "Run `go-deeper` on a new task, unless it already ran for this task or its skip rule applies.",
        },
    ),
    (
        "route-declaration",
        "assistant-text",
        {
            "swe": "Say `Playbook: <slug>. Reason: <one clause>.`",
            "lab": "Say `Playbook: <slug>. Reason: <one clause>.`",
        },
    ),
    (
        "read-playbook-in-full",
        "full-read",
        {
            "swe": "For a playbook, read `playbooks/<slug>.md` in full.",
            "lab": "For a playbook, read `playbooks/<slug>.md` in full.",
        },
    ),
    (
        "one-task-per-step",
        "task-list",
        {
            "swe": "create one task per step right after you read the playbook or load the routed skill. "
            "Copy each playbook step line byte for byte",
            "lab": "create one task per step. Copy each playbook step line byte for byte, in file order.",
        },
    ),
    (
        "load-names-before-step",
        "task-list",
        {
            "swe": "Before a step, load each name in its parentheses that you have not loaded in this session.",
            "lab": "Before a step, load each name in its parentheses that you have not loaded in this session",
        },
    ),
    (
        "steps-section",
        "final-reply-section",
        {
            "swe": 'End your final reply with a "Steps" section that gives every handle in order with its state.',
            "lab": 'End the final reply with a "Steps" section that gives every step handle in order with its state.',
        },
    ),
    (
        "re-match-on-new-task",
        "assistant-text",
        {
            "swe": 'Match again each time this skill is invoked and whenever the user says "new task".',
            "lab": 'Match again each time this skill is invoked and whenever the user says "new task".',
        },
    ),
    (
        "delegate-brief-router-path",
        "agent-spawn",
        {
            "swe": "Put this file's absolute path in every delegate's brief.",
            "lab": "Put this file's absolute path in every delegate's brief.",
        },
    ),
    (
        "first-message-restatement",
        "assistant-text",
        {
            "swe": "Your first message on a task: tell the user, in your own words, their goal",
            "lab": "Your first message on a task: restate the question in your own words",
        },
    ),
    (
        "principle-citation",
        "final-reply-section",
        {
            "swe": "In the final reply, name each principle that changed a decision and the choice it changed.",
            "lab": "In the final reply, name each principle that changed a decision and the choice it changed.",
        },
    ),
    (
        "cite-only-loaded-principles",
        "final-reply-section",
        {"swe": "Cite only principles you loaded in this session."},
    ),
    (
        "ship-pr-before-first-commit",
        "skill-call",
        {"swe": "before the first commit. Its rules govern each commit"},
    ),
    (
        "research-context-before-first-step",
        "skill-call-or-full-read",
        {
            "lab": "The repository has a `research-context` project skill: load it before the first step."
        },
    ),
    (
        "load-names-in-listed-order",
        "task-list",
        {"lab": "that you have not loaded in this session, in the order listed."},
    ),
    (
        "pick-one-rule",
        "skill-call",
        {
            "lab": "When the step text picks one of two names, load only the one it picks."
        },
    ),
]

STEP = re.compile(r"(\d+-[a-z0-9-]+): (.+)")
REPLY = re.compile(r"Reply: (.+)")
PARENS = re.compile(r"\(([^()]+)\)\s*$")
NAME = re.compile(r"[a-z][a-z0-9-]*|reviewer agent")
CONDITIONAL = re.compile(r"^When |\bSkip (when|for)\b")
TRANSITIVE_FORMS = (
    re.compile(r"[Ss]teps (\d+) to (\d+) of ([a-z0-9-]+)"),
    re.compile(r"\b([a-z0-9-]+) steps (\d+) to (\d+)"),
)
STEP_MENTION = re.compile(r"\b[Ss]teps? \d+")


class FacetError(Exception):
    pass


def norm(text):
    return " ".join(text.split())


def rel(path):
    return path.relative_to(REPO).as_posix()


def frontmatter(path):
    lines = path.read_text(encoding="utf-8").split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        raise FacetError(f"{rel(path)}: no frontmatter")
    fields = {}
    for line in lines[1 : lines.index("---", 1)]:
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            value = value.strip()
            fields[key.strip()] = json.loads(value) if value.startswith('"') else value
    return fields


def section(path, heading):
    lines = path.read_text(encoding="utf-8").split("\n")
    if f"## {heading}" not in lines:
        raise FacetError(f"{rel(path)}: no '## {heading}' section")
    body = []
    for line in lines[lines.index(f"## {heading}") + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def bullets(lines):
    items = []
    for line in lines:
        if line.startswith("- "):
            items.append(line[2:])
        elif items and line.startswith(" ") and line.strip() and items[-1] is not None:
            items[-1] += " " + line.strip()
        else:
            items.append(None)
    return [norm(item) for item in items if item is not None]


def leading_slug(bullet, path, heading):
    match = re.match(r"`([a-z0-9-]+)`: ", bullet)
    if not match:
        raise FacetError(
            f"{rel(path)}: '{heading}' bullet does not start with a backticked slug: {bullet}"
        )
    return match.group(1)


class Resolution(NamedTuple):
    name_class: str
    evidence: str
    scorer: str
    path: str | None


class Plugin:
    def __init__(self, name):
        self.name = name
        self.root = PLUGINS / name
        self.visible, self.hidden, self.principles = {}, {}, {}
        for file in sorted(self.root.glob("skills/*/SKILL.md")):
            skill = file.parent.name
            hidden = frontmatter(file).get("disable-model-invocation") == "true"
            if skill.startswith("principle-"):
                if not hidden:
                    raise FacetError(
                        f"{rel(file)}: a principle must set disable-model-invocation: true"
                    )
                self.principles[skill[len("principle-") :]] = file
            else:
                (self.hidden if hidden else self.visible)[skill] = file
        self.router = ROUTERS.get(name)
        self.router_file, self.playbooks, self.references = None, {}, {}
        if self.router:
            router_dir = self.root / "skills" / self.router
            self.router_file = router_dir / "SKILL.md"
            self.playbooks = {
                p.stem: p for p in sorted(router_dir.glob("playbooks/*.md"))
            }
            self.references = {
                p.stem: p for p in sorted(router_dir.glob("references/*.md"))
            }
        self.project = PROJECT_SKILL_ANCHORS.get(name, {})

    def plugin_path(self, file):
        return file.relative_to(self.root).as_posix()

    def resolve(self, name):
        classes = (
            (
                name == "reviewer agent",
                "reviewer-agent",
                "agent-spawn",
                "invisible",
                None,
            ),
            (
                name in self.principles,
                "principle",
                "full-read",
                "recorded",
                f"skills/principle-{name}/SKILL.md",
            ),
            (
                name in self.hidden,
                "hidden-skill",
                "full-read",
                "recorded",
                f"skills/{name}/SKILL.md",
            ),
            (name in self.visible, "visible-skill", "skill-call", "recorded", None),
            (
                name in self.playbooks,
                "playbook",
                "full-read",
                "recorded",
                self.plugin_path(self.playbooks[name])
                if name in self.playbooks
                else None,
            ),
            (
                name in self.references,
                "reference",
                "full-read",
                "recorded",
                self.plugin_path(self.references[name])
                if name in self.references
                else None,
            ),
            (
                name in self.project,
                "project-skill",
                "skill-call-or-full-read",
                "invisible",
                f".agents/skills/{name}/SKILL.md",
            ),
        )
        matches = [row for row in classes if row[0]]
        if len(matches) > 1:
            raise FacetError(
                f"{name!r} in {self.name} matches more than one class: "
                f"{', '.join(row[1] for row in matches)}"
            )
        return Resolution(*matches[0][1:]) if matches else None


def make(
    kind,
    plugin,
    subject,
    tail=(),
    *,
    required_by,
    locator,
    source_text,
    requirement="always",
    evidence=None,
    path=None,
    scorer=None,
    cases=None,
    **extra,
):
    spec = KINDS[kind]
    record = {
        "id": "/".join(
            [kind, plugin, subject, *(t.replace(" ", "-").lower() for t in tail)]
        ),
        "kind": kind,
        "plugin": plugin,
        "subject": subject,
        "evidence": evidence or spec["evidence"],
        "path": path,
        "required_by": {"path": rel(required_by), "locator": locator},
        "source_text": norm(source_text),
        "requirement": requirement,
        "scope": spec["scope"],
        "scorer": scorer or spec["scorer"],
        "cases": cases or {"positive": [], "negative": []},
    }
    record.update(extra)
    return record


def coverage():
    skills = skill_eval.catalog_skills()
    resolve = skill_eval.resolver(skills)
    cases = defaultdict(lambda: {"positive": [], "negative": []})
    routes, listed = defaultdict(list), defaultdict(list)
    for case in skill_eval.corpus():
        if skill_eval.excluded(case, resolve, skills):
            continue
        side = "negative" if case["category"] == "negative" else "positive"
        cases[resolve(case["target"])][side].append(case["id"])
        if case.get("expected_route"):
            routes[tuple(case["expected_route"].split("/")[1:])].append(case["id"])
        for facet_id in case.get("facets", []):
            listed[facet_id].append(case["id"])
    return {resolve(t) for t in skill_eval.TARGETS}, cases, routes, listed


def mark_scored(facets, routes, listed):
    """A case's expected_route scores its route facets; its facets field scores the ones it lists."""
    for f in facets:
        ids = listed.get(f["id"], [])
        conditional_load = f["kind"] == "step-load" and f.get("requirement") == "transitive" and f.get("conditional")
        if f["kind"] in {"route", "route-load", "playbook-read", "step-load"} and not conditional_load:
            ids = ids + routes.get((f["plugin"], f["subject"]), [])
        if ids and (f["kind"] == "route" or f["scorer"] == "recorded"):
            f["scorer"] = "scored"
            f["cases"] = {"positive": sorted(set(ids)), "negative": []}


def activation_facets(plugin, targets, cases):
    for skill, file in plugin.visible.items():
        key = f"{plugin.name}:{skill}"
        description = frontmatter(file).get("description")
        if not description:
            raise FacetError(f"{rel(file)}: no description")
        found = cases.get(key, {"positive": [], "negative": []})
        yield make(
            "activation",
            plugin.name,
            skill,
            required_by=file,
            locator="description",
            source_text=description,
            scorer="scored" if key in targets else "recorded",
            cases={side: sorted(ids) for side, ids in found.items()},
        )


def hook_facets(plugin):
    hook = plugin.root / "hooks" / "session-start.md"
    if not hook.exists():
        return
    text = hook.read_text(encoding="utf-8")
    sentences = re.split(r"(?<=\.)\s+", norm(text))
    named = re.findall(r"`([a-z]+):([a-z][a-z0-9-]*)`", text) + [
        (plugin.name, skill) for skill in re.findall(r"the `([a-z][a-z0-9-]*)` skill", text)
    ]
    for owner, skill in dict.fromkeys(named):
        if owner != plugin.name or skill not in plugin.visible | plugin.hidden:
            raise FacetError(
                f"{rel(hook)}: names `{owner}:{skill}`, which is not a {plugin.name} skill"
            )
        sentence = next(
            s for s in sentences if f"`{owner}:{skill}`" in s or f"the `{skill}` skill" in s
        )
        yield make(
            "hook-load",
            plugin.name,
            skill,
            required_by=hook,
            locator=f"{owner}:{skill}",
            source_text=sentence,
            requirement="conditional",
        )


def parse_playbook(plugin, slug, file):
    rows = []
    for line in file.read_text(encoding="utf-8").split("\n"):
        step, reply = STEP.fullmatch(line), REPLY.fullmatch(line)
        if step:
            rows.append((step.group(1), step.group(2), line))
        elif reply:
            rows.append(("Reply", reply.group(1), line))
    handles = [h for h, _, _ in rows]
    if len(set(handles)) != len(handles):
        raise FacetError(f"{rel(file)}: duplicate step handle")
    return rows


def step_names(plugin, file, handle, text):
    match = PARENS.search(text)
    names = match.group(1).split(", ") if match else []
    for name in names:
        if not NAME.fullmatch(name):
            raise FacetError(
                f"{rel(file)}: step {handle} has a parenthesized name that is not a name: {name!r}"
            )
    return names


def resolved(plugin, name, file, locator):
    found = plugin.resolve(name)
    if found is None:
        raise FacetError(
            f"{rel(file)}: {locator} names {name!r}, which no skill, principle, playbook, "
            f"reference, or project skill of {plugin.name} owns"
        )
    return found


def load_facet(
    kind, plugin, subject, tail, name, file, locator, source_text, requirement, **extra
):
    found = resolved(plugin, name, file, locator)
    return make(
        kind,
        plugin.name,
        subject,
        tail,
        required_by=file,
        locator=locator,
        source_text=source_text,
        requirement=requirement,
        evidence=found.evidence,
        scorer=found.scorer,
        path=found.path,
        name=name,
        name_class=found.name_class,
        **extra,
    )


def transitive_runs(plugin, file, slug, handle, text, names):
    if plugin.name not in TRANSITIVE:
        return []
    playbooks = [name for name in names if name in plugin.playbooks]
    if not playbooks:
        return []
    runs = []
    whole = WHOLE_RUNS.get((plugin.name, slug, handle))
    if whole:
        runs.append((whole, None))
    elif "Run the playbook" in text:
        raise FacetError(
            f"{rel(file)}: step {handle} runs a whole playbook that WHOLE_RUNS does not declare: {text}"
        )
    of_form, slug_form = TRANSITIVE_FORMS
    before = {m.end(1) + 1: m for m in slug_form.finditer(text)}
    for mention in STEP_MENTION.finditer(text):
        of_match = of_form.match(text, mention.start())
        if of_match:
            first, last, target = of_match.groups()
        elif mention.start() in before:
            target, first, last = before[mention.start()].groups()
        else:
            target = None
        if target not in playbooks:
            raise FacetError(
                f"{rel(file)}: step {handle} names steps, but only two forms parse: "
                f'"steps N to M of <playbook>" and "<playbook> steps N to M", '
                f"where <playbook> is a parenthesized playbook: {text}"
            )
        runs.append((target, range(int(first), int(last) + 1)))
    return runs


def run_supplies(plugin, steps, file, handle, runs):
    supplies = []
    for target, numbers in runs:
        numbered = {
            int(h.split("-", 1)[0]): (h, t) for h, t, _ in steps[target] if h != "Reply"
        }
        numbers = numbered if numbers is None else numbers
        if not set(numbers) <= set(numbered):
            raise FacetError(
                f"{rel(file)}: step {handle} runs steps {min(numbers)} to {max(numbers)} "
                f"of {target}, which has no such steps"
            )
        for number in sorted(numbers):
            target_handle, target_text = numbered[number]
            names = step_names(
                plugin, plugin.playbooks[target], target_handle, target_text
            )
            supplies.append(((target, target_handle, target_text), names))
    return supplies


def unlisted_names_merged_by_name(listed, supplies):
    merged = defaultdict(list)
    for supplier, names in supplies:
        for name in names:
            if name not in listed:
                merged[name].append(supplier)
    return merged


def check_declared_steps(plugin, steps):
    for owner, slug, handle in ONE_OF:
        if owner == plugin.name and handle not in [
            h for h, _, _ in steps.get(slug, [])
        ]:
            raise FacetError(
                f"ONE_OF names step {handle} of {owner} playbook {slug!r}, which does not exist"
            )
    for (owner, slug, handle), target in WHOLE_RUNS.items():
        if owner != plugin.name:
            continue
        row = next((r for r in steps.get(slug, []) if r[0] == handle), None)
        if row is None:
            raise FacetError(
                f"WHOLE_RUNS names step {handle} of {owner} playbook {slug!r}, which does not exist"
            )
        if target not in plugin.playbooks:
            raise FacetError(
                f"WHOLE_RUNS targets {target!r} for step {handle} of {owner} playbook {slug!r}, which is not a playbook"
            )
        file = plugin.playbooks[slug]
        if target not in step_names(plugin, file, handle, row[1]):
            raise FacetError(
                f"{rel(file)}: WHOLE_RUNS says step {handle} runs {target}, "
                f"which its parentheses do not name"
            )
        if "Run the playbook" not in row[1]:
            raise FacetError(
                f"{rel(file)}: WHOLE_RUNS says step {handle} runs {target}, "
                f"but it no longer says 'Run the playbook'"
            )


def playbook_facets(plugin, steps):
    check_declared_steps(plugin, steps)
    for slug, file in plugin.playbooks.items():
        for handle, text, line in steps[slug]:
            names = step_names(plugin, file, handle, text)
            override = ONE_OF.get((plugin.name, slug, handle), ())
            if set(override) - set(names):
                raise FacetError(
                    f"{rel(file)}: ONE_OF names {sorted(set(override) - set(names))} "
                    f"that step {handle} does not list"
                )
            direct = {}
            for name in names:
                requirement = (
                    "conditional"
                    if CONDITIONAL.search(text)
                    else "one-of"
                    if name in override
                    else "always"
                )
                facet = load_facet(
                    "reply-load" if handle == "Reply" else "step-load",
                    plugin,
                    slug,
                    (handle, name),
                    name,
                    file,
                    handle,
                    line,
                    requirement,
                    handle=handle,
                )
                direct[name] = facet["id"]
                yield facet
            runs = transitive_runs(plugin, file, slug, handle, text, names)
            supplies = run_supplies(plugin, steps, file, handle, runs)
            for name, suppliers in unlisted_names_merged_by_name(
                {*names, slug}, supplies
            ).items():
                targets = sorted({target for target, _, _ in suppliers})
                if len(targets) > 1:
                    raise FacetError(
                        f"{rel(file)}: step {handle} gets {name!r} from {targets}; "
                        f"a transitive facet has one via"
                    )
                yield load_facet(
                    "step-load",
                    plugin,
                    slug,
                    (handle, name),
                    name,
                    file,
                    handle,
                    line,
                    "transitive",
                    handle=handle,
                    via=direct[targets[0]],
                    target_handles=[f"{t}/{h}" for t, h, _ in suppliers],
                    conditional=bool(
                        CONDITIONAL.search(text)
                        or all(CONDITIONAL.search(t) for _, _, t in suppliers)
                    ),
                )


def router_facets(plugin):
    router = plugin.router_file
    text = norm(router.read_text(encoding="utf-8"))
    if plugin.name in TRANSITIVE and norm(TRANSITIVE[plugin.name]) not in text:
        raise FacetError(
            f"{rel(router)}: the transitive load rule is gone: {TRANSITIVE[plugin.name]!r}"
        )
    for name, anchor in plugin.project.items():
        if norm(anchor) not in text:
            raise FacetError(
                f"{rel(router)}: project skill {name} lost its anchor {anchor!r}"
            )
    listed = {}
    for bullet in bullets(section(router, "Playbooks")):
        listed[leading_slug(bullet, router, "Playbooks")] = bullet
    if set(listed) != set(plugin.playbooks):
        raise FacetError(
            f"{rel(router)}: Playbooks entries {sorted(set(listed) ^ set(plugin.playbooks))} "
            f"do not match the playbook files one to one"
        )
    steps = {
        slug: parse_playbook(plugin, slug, file)
        for slug, file in plugin.playbooks.items()
    }
    for slug, bullet in listed.items():
        locator = f"Playbooks: {slug}"
        yield make(
            "route",
            plugin.name,
            slug,
            required_by=router,
            locator=locator,
            source_text=bullet,
            route_type="playbook",
            handles=[h for h, _, _ in steps[slug] if h != "Reply"],
        )
        yield make(
            "playbook-read",
            plugin.name,
            slug,
            required_by=router,
            locator=locator,
            source_text=bullet,
            path=plugin.plugin_path(plugin.playbooks[slug]),
        )
    routes = defaultdict(list)
    for bullet in bullets(section(router, "Single-skill routes")):
        names = re.findall(r"`([^`]+)`", bullet)
        if not names or names[-1] not in plugin.visible | plugin.hidden:
            raise FacetError(
                f"{rel(router)}: Single-skill route does not end in a {plugin.name} skill: {bullet}"
            )
        if names[-1] in plugin.playbooks:
            raise FacetError(
                f"{rel(router)}: routed skill {names[-1]} shares a name with a playbook"
            )
        routes[names[-1]].append(bullet)
    extra = {}
    for (owner, skill), anchor in EXTRA_ROUTES.items():
        if owner != plugin.name:
            continue
        if norm(anchor) not in text:
            raise FacetError(
                f"{rel(router)}: route to {skill} lost its anchor {anchor!r}"
            )
        if skill not in plugin.visible | plugin.hidden:
            raise FacetError(
                f"{rel(router)}: extra route names {skill}, which is not a skill"
            )
        if skill in routes:
            raise FacetError(
                f"{rel(router)}: {skill} is a Single-skill route; drop it from EXTRA_ROUTES"
            )
        extra[skill] = anchor
    for locator, skill, source_text in [
        (f"Single-skill routes: {skill}", skill, " | ".join(texts))
        for skill, texts in routes.items()
    ] + [(f"Match: {skill}", skill, anchor) for skill, anchor in extra.items()]:
        yield make(
            "route",
            plugin.name,
            skill,
            required_by=router,
            locator=locator,
            source_text=source_text,
            route_type="skill",
            handles=[],
        )
        yield load_facet(
            "route-load",
            plugin,
            skill,
            (),
            skill,
            router,
            locator,
            source_text,
            "always",
        )
    yield from playbook_facets(plugin, steps)
    triggers = defaultdict(list)
    for bullet in bullets(section(router, "Triggers")):
        for token in dict.fromkeys(re.findall(r"`([^`]+)`", bullet)):
            if (plugin.name, token) in TRIGGER_IGNORE:
                continue
            if not NAME.fullmatch(token) or plugin.resolve(token) is None:
                raise FacetError(
                    f"{rel(router)}: Triggers token {token!r} is not a loadable "
                    f"{plugin.name} name; classify it or add it to TRIGGER_IGNORE"
                )
            triggers[token].append(bullet)
    for token, texts in triggers.items():
        yield load_facet(
            "trigger-load",
            plugin,
            plugin.router,
            (token,),
            token,
            router,
            "Triggers",
            " | ".join(texts),
            "conditional",
        )
    for slug, evidence, anchors in CONTRACTS:
        if plugin.name not in anchors:
            continue
        anchor = norm(anchors[plugin.name])
        if anchor not in text:
            raise FacetError(
                f"{rel(router)}: router contract {slug} lost its anchor {anchor!r}"
            )
        path = (
            f"skills/{plugin.router}/playbooks/<slug>.md"
            if evidence == "full-read"
            else None
        )
        yield make(
            "router-contract",
            plugin.name,
            slug,
            required_by=router,
            locator=anchor,
            source_text=anchor,
            evidence=evidence,
            path=path,
        )


def principle_facets(plugin, loads):
    if not plugin.principles:
        return
    if plugin.router is None:
        raise FacetError(f"plugins/{plugin.name}: principles without a router")
    listed = {}
    for bullet in bullets(section(plugin.router_file, "Principles")):
        listed[leading_slug(bullet, plugin.router_file, "Principles")] = bullet
    if set(listed) != set(plugin.principles):
        raise FacetError(
            f"{rel(plugin.router_file)}: Principles entries "
            f"{sorted(set(listed) ^ set(plugin.principles))} do not match the principle folders"
        )
    for slug, file in plugin.principles.items():
        reaching = [f for f in loads if f["name"] == slug]
        always = any(
            f["kind"] == "step-load" and f["requirement"] == "always" for f in reaching
        )
        yield make(
            "principle-read",
            plugin.name,
            slug,
            required_by=plugin.router_file,
            locator=f"Principles: {slug}",
            source_text=listed[slug],
            path=plugin.plugin_path(file),
            requirement="always" if always else "conditional",
            reached_from=sorted(f["id"] for f in reaching),
            router_only=not any(f["kind"] == "step-load" for f in reaching),
        )


def build():
    targets, cases, routes, listed = coverage()
    facets, unreached = [], {}
    for root in sorted(p for p in PLUGINS.iterdir() if (p / "skills").is_dir()):
        plugin = Plugin(root.name)
        own = list(activation_facets(plugin, targets, cases)) + list(
            hook_facets(plugin)
        )
        if plugin.router:
            own += list(router_facets(plugin))
        loads = [f for f in own if f["kind"] in {"step-load", "trigger-load"}]
        own += list(principle_facets(plugin, loads))
        reached = {
            f["name"]
            for f in own
            if f["kind"] in {"step-load", "reply-load", "trigger-load", "route-load"}
        }
        unreached[plugin.name] = sorted(set(plugin.hidden) - reached)
        facets += own
    ids = Counter(f["id"] for f in facets)
    if any(n > 1 for n in ids.values()):
        raise FacetError(
            f"duplicate facet ids: {sorted(i for i, n in ids.items() if n > 1)}"
        )
    dangling = sorted(f["id"] for f in facets if "via" in f and f["via"] not in ids)
    if dangling:
        raise FacetError(f"transitive facets whose via is no facet: {dangling}")
    mark_scored(facets, routes, listed)
    facets.sort(key=lambda f: f["id"])
    summary = defaultdict(Counter)
    for f in facets:
        summary[f["kind"]][f["scorer"]] += 1
    data = {
        "schema_version": 1,
        "summary": {k: dict(sorted(v.items())) for k, v in sorted(summary.items())},
        "facets": facets,
    }
    return data, unreached


def strip_links(text):
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def cell(value):
    return strip_links(str(value)).replace("|", "\\|")


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return lines + [""]


def count(cases):
    return len(cases["positive"]), len(cases["negative"])


def render(data, unreached):
    facets = data["facets"]
    by_kind = defaultdict(list)
    for f in facets:
        by_kind[f["kind"]].append(f)
    behaviors = defaultdict(list)
    for f in facets:
        if f["requirement"] == "always":
            key = (
                (f["plugin"], f["subject"], f["name"])
                if f["kind"] == "step-load"
                else f["id"]
            )
            behaviors[key].append(f)
    uncovered = [
        key
        for key, group in behaviors.items()
        if not any(sum(count(f["cases"])) for f in group)
    ]
    scorers = list(SCORERS)
    out = [
        "<!-- Generated by evals/skills/facets.py. Do not edit; run `uv run evals/skills/facets.py write`. -->",
        "",
        "# Eval facet map",
        "",
        f"{len(uncovered)} of {len(behaviors)} always-required behaviors have no scoring case. "
        "The count is approximate. A step load counts once per playbook and name. "
        "A condition in the middle of a step leaves its names `always`.",
        "",
        "## Legend",
        "",
    ]
    out += table(
        ["kind", "meaning"], [(f"`{k}`", v["about"]) for k, v in KINDS.items()]
    )
    out += table(["evidence", "meaning"], [(f"`{k}`", v) for k, v in EVIDENCE.items()])
    out += [
        (
            "Every read can also happen through Bash (`cat`, `sed`). "
            "The scorer records a Bash read that mentions a frozen path as `unproved`, "
            "and never counts it."
        ),
        "",
    ]
    out += table(
        ["requirement", "meaning"], [(f"`{k}`", v) for k, v in REQUIREMENTS.items()]
    )
    out += table(["scope", "meaning"], [(f"`{k}`", v) for k, v in SCOPES.items()])
    out += table(["scorer", "meaning"], [(f"`{k}`", v) for k, v in SCORERS.items()])
    out += ["## Summary", ""]
    out += table(
        ["kind", *scorers, "total"],
        [
            (
                k,
                *(data["summary"][k].get(s, 0) for s in scorers),
                sum(data["summary"][k].values()),
            )
            for k in KINDS
            if k in data["summary"]
        ],
    )
    out += ["## Activation", ""]
    out += table(
        ["skill", "plugin", "positive cases", "negative cases", "scorer"],
        [
            (f["subject"], f["plugin"], *count(f["cases"]), f["scorer"])
            for f in by_kind["activation"]
        ],
    )
    out += ["### Activation facets with no case", ""]
    out += [
        f"- `{f['plugin']}:{f['subject']}`"
        for f in by_kind["activation"]
        if not sum(count(f["cases"]))
    ]
    out += [""]
    for plugin, router in ROUTERS.items():
        mine = [f for f in facets if f["plugin"] == plugin]
        out += [f"## Router `{router}` ({plugin})", "", "### Routes", ""]
        out += table(
            ["route", "handles", "positive cases", "negative cases"],
            [
                (
                    f"{f['route_type']} `{f['subject']}`",
                    ", ".join(f["handles"]) or "-",
                    *count(f["cases"]),
                )
                for f in mine
                if f["kind"] == "route"
            ],
        )
        handles = {
            f["subject"]: f["handles"] + ["Reply"]
            for f in mine
            if f.get("route_type") == "playbook"
        }
        for f in mine:
            if f["kind"] != "playbook-read":
                continue
            steps = sorted(
                (
                    s
                    for s in mine
                    if s["kind"] in {"step-load", "reply-load"} and s["subject"] == f["subject"]
                ),
                key=lambda s: handles[f["subject"]].index(s["handle"]),
            )
            out += [f"### Playbook `{f['subject']}` step loads", ""]
            out += table(
                [
                    "handle",
                    "name",
                    "name class",
                    "evidence",
                    "requirement",
                    "supplied by",
                ],
                [
                    (
                        s["handle"],
                        s["name"],
                        s["name_class"],
                        s["evidence"],
                        s["requirement"]
                        + (", conditional" if s.get("conditional") else ""),
                        ", ".join(s.get("target_handles", [])) or "-",
                    )
                    for s in steps
                ],
            )
        out += ["### Route loads", ""]
        out += table(
            ["skill", "name class", "evidence", "scorer", "route"],
            [
                (
                    f["name"],
                    f["name_class"],
                    f["evidence"],
                    f["scorer"],
                    f["required_by"]["locator"],
                )
                for f in mine
                if f["kind"] == "route-load"
            ],
        )
        out += ["### Trigger loads", ""]
        out += table(
            ["name", "name class", "evidence", "scorer", "trigger"],
            [
                (
                    f["name"],
                    f["name_class"],
                    f["evidence"],
                    f["scorer"],
                    f["source_text"],
                )
                for f in mine
                if f["kind"] == "trigger-load"
            ],
        )
        out += ["### Router contracts", ""]
        out += table(
            ["contract", "evidence", "anchor phrase"],
            [
                (f["subject"], f["evidence"], f["source_text"])
                for f in mine
                if f["kind"] == "router-contract"
            ],
        )
    out += ["## Principles", ""]
    out += table(
        ["plugin", "principle", "requirement", "router only", "reached from"],
        [
            (
                f["plugin"],
                f["subject"],
                f["requirement"],
                "yes" if f["router_only"] else "no",
                "<br>".join(f["reached_from"]) or "-",
            )
            for f in by_kind["principle-read"]
        ],
    )
    out += ["## Hook loads", ""]
    out += table(
        ["plugin", "skill", "scorer", "hook sentence"],
        [
            (f["plugin"], f["subject"], f["scorer"], f["source_text"])
            for f in by_kind["hook-load"]
        ],
    )
    out += [
        "## Hidden skills that nothing reaches",
        "",
        "No route, step, or trigger names these hidden, non-principle skills. This is information, not an error.",
        "",
    ]
    out += [
        f"- `{plugin}:{skill}`"
        for plugin, skills in unreached.items()
        for skill in skills
    ] or ["- none"]
    return "\n".join(out) + "\n"


def outputs():
    data, unreached = build()
    return {
        JSON_OUT: json.dumps(data, indent=2, sort_keys=True) + "\n",
        MD_OUT: render(data, unreached),
    }


def check(expected):
    stale = 0
    for path, text in expected.items():
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != text:
            stale = 1
            diff = list(
                difflib.unified_diff(
                    current.splitlines(),
                    text.splitlines(),
                    rel(path) + " (checked in)",
                    rel(path) + " (from sources)",
                    lineterm="",
                    n=1,
                )
            )
            print("\n".join(diff[:40]))
    if stale:
        print(
            "facets: the facet map is stale; run `uv run evals/skills/facets.py write`",
            file=sys.stderr,
        )
    return stale


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("write", "check"))
    args = parser.parse_args()
    try:
        expected = outputs()
    except (FacetError, ValueError, KeyError, OSError) as error:
        parser.exit(2, f"facets: {error}\n")
    if args.command == "write":
        for path, text in expected.items():
            path.write_text(text, encoding="utf-8")
        return 0
    return check(expected)


if __name__ == "__main__":
    sys.exit(main())
