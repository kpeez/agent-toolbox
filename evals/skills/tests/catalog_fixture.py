import json
import shutil
from pathlib import Path

from corpus_io import write_corpus

HERE = Path(__file__).resolve().parents[1]

SKILLS = {
    "swe": ("swe-mode implement diagnose verifying-work codebase-design interview-user ship-pr go-deeper writing "
            "in-your-own-words figure-it-out blast-radius log-decisions architect why recall "
            "principle-model-the-domain").split(),
    "lab": ("lab-mode go-deeper making-plots autoresearch research principle-write-the-decision-first "
            "principle-grade-the-evidence principle-encode-the-procedure principle-simulate-before-you-trust").split(),
    "uni": ["go-deeper"],
}
BODIES = {"swe:swe-mode": "# swe-mode: route a task to its playbook\n\nTask: $ARGUMENTS\n",
          "swe:recall": "List the sessions, except this one: ${CLAUDE_SESSION_ID}\n"}
ROUTER = {"swe": "swe-mode", "lab": "lab-mode"}
REFERENCES = {"lab": ["claim-checklist"]}
PLAYBOOK_STEPS = {
    ("lab", "analyze-results"): [("1-locate-raw-results", "claim-checklist"),
                                 ("2-state-the-decision", "write-the-decision-first"),
                                 ("4-check-the-pipeline", "simulate-before-you-trust", "conditional"),
                                 ("9-make-figures", "making-plots"), ("10-grade-the-conclusion", "grade-the-evidence"),
                                 ("11-feed-the-flywheel", "encode-the-procedure")],
    ("lab", "run-experiment"): [("1-write-the-decision", "write-the-decision-first"),
                                ("4-pilot-small", "simulate-before-you-trust"), ("7-analyze", "analyze-results")],
    ("lab", "bootstrap-project"): [("3-prove-the-context", "research-context")],
    ("swe", "build-feature"): [("1-plan-the-change", "verifying-work")],
    ("swe", "investigate-question"): [("1-read-the-code", "why")],
    ("swe", "refactor-structure"): [("1-name-the-seam", "architect")],
    ("swe", "fix-bug"): [("1-reproduce-failure", "diagnose")],
}
PLAYBOOKS = {plugin: [slug for p, slug in PLAYBOOK_STEPS if p == plugin] for plugin in ROUTER}
TRANSITIVE = {("lab", "run-experiment", "7-analyze"): [("grade-the-evidence", False), ("making-plots", False),
                                                       ("simulate-before-you-trust", True)]}
SKILL_ROUTES = {("lab", "autoresearch"): {"modes": {
                    "run": ["1-set-up-the-program", "2-establish-the-baseline", "3-run-the-candidate-loop"],
                    "cleanup": ["1-recover-the-evidence", "2-archive-and-retain"]}},
                ("lab", "making-plots"): {"handles": ["1-read-the-data", "2-draw-the-figure", "3-review-the-figure"]},
                ("swe", "figure-it-out"): {}, ("swe", "blast-radius"): {}, ("swe", "diagnose"): {}}
TRIGGERS = {"swe": ["writing", "in-your-own-words", "log-decisions", "architect", "model-the-domain"]}


def target(plugin, name):
    folder = f"skills/{ROUTER.get(plugin)}"
    if name == "research-context":
        return ".agents/skills/research-context/SKILL.md", "skill-call-or-full-read", "project-skill"
    if f"principle-{name}" in SKILLS[plugin]:
        return f"skills/principle-{name}/SKILL.md", "full-read", "principle"
    if name in REFERENCES.get(plugin, []):
        return f"{folder}/references/{name}.md", "full-read", "reference"
    if name in PLAYBOOKS[plugin]:
        return f"{folder}/playbooks/{name}.md", "full-read", "playbook"
    return None, "skill-call", "visible-skill"


def facet(kind, plugin, subject, name=None, handle=None, scope="delegate-allowed", requirement="always", **extra):
    path, evidence, name_class = target(plugin, name) if name else (None, "assistant-text", None)
    return {"id": "/".join(p for p in (kind, plugin, subject, handle, name) if p), "kind": kind, "plugin": plugin,
            "subject": subject, "name": name, "handle": handle, "path": path, "evidence": evidence,
            "name_class": name_class, "scope": scope, "requirement": requirement, **extra}


def facets():
    found = []
    for (plugin, slug), steps in PLAYBOOK_STEPS.items():
        found.append(facet("route", plugin, slug, scope="root", route_type="playbook", handles=[s[0] for s in steps]))
        found.append(facet("playbook-read", plugin, slug, scope="root") | {
            "path": f"skills/{ROUTER[plugin]}/playbooks/{slug}.md", "evidence": "full-read"})
        for handle, name, *requirement in steps:
            found.append(facet("step-load", plugin, slug, name, handle, requirement=(requirement or ["always"])[0]))
            for extra, conditional in TRANSITIVE.get((plugin, slug, handle), []):
                found.append(facet("step-load", plugin, slug, extra, handle, requirement="transitive",
                                   conditional=conditional))
    for (plugin, skill), shape in SKILL_ROUTES.items():
        found.append(facet("route", plugin, skill, scope="root", route_type="skill", **{"handles": [], **shape}))
        found.append(facet("route-load", plugin, skill, skill, scope="root"))
    for plugin, names in TRIGGERS.items():
        found += [facet("trigger-load", plugin, ROUTER[plugin], name, requirement="conditional") for name in names]
    return {"schema_version": 1, "facets": sorted(found, key=lambda f: f["id"])}


def case(case_id, target_skill, category, route=None, expected=None, aux=(), forbidden=(), **extra):
    if expected is None:
        expected = [] if category == "negative" else [target_skill]
    return {"id": case_id, "target": target_skill, "category": category, "split": "holdout",
            "expected_skills": list(expected), "acceptable_auxiliaries": list(aux), "forbidden_skills": list(forbidden),
            "relevant_action": f"Act on the {case_id} request.", "rationale": "A scorer fixture case.",
            "messages": [{"role": "user", "content": f"The {case_id} request."}], "fixture": "small-repo",
            **({"expected_route": route} if route else {}), **extra}


SWE_ROUTER = ["swe:swe-mode", "swe:go-deeper"]
CASES = [
    case("implement-build-feature", "swe:implement", "natural", "route/swe/build-feature", aux=["swe:verifying-work"]),
    case("implement-negative-diagnose", "swe:implement", "negative", "route/swe/diagnose", expected=["swe:diagnose"],
         forbidden=["swe:implement"]),
    case("implement-skip-go-deeper", "swe:implement", "explicit", "route/swe/build-feature",
         aux=["swe:verifying-work"], forbidden=["swe:go-deeper"]),
    case("codebase-design-labels-the-router", "swe:codebase-design", "natural", aux=SWE_ROUTER),
    case("interview-user-quick-fact", "swe:interview-user", "negative", aux=["swe:swe-mode"],
         forbidden=["swe:interview-user", "swe:go-deeper"]),
    case("ship-pr-read-only", "swe:ship-pr", "negative", aux=SWE_ROUTER, forbidden=["swe:ship-pr"]),
    case("verifying-work-read-only", "swe:verifying-work", "negative", aux=["swe:swe-mode"],
         forbidden=["swe:verifying-work", "swe:go-deeper"]),
    case("diagnose-route", "swe:diagnose", "natural", "route/swe/diagnose"),
    case("swe-mode-refactor-structure", "swe:swe-mode", "natural", "route/swe/refactor-structure"),
    case("swe-route-figure-it-out", "swe:swe-mode", "natural", "route/swe/figure-it-out", family="swe-route-choice"),
    case("swe-route-blast-radius", "swe:swe-mode", "natural", "route/swe/blast-radius", family="swe-route-choice"),
    case("swe-mode-chat", "swe:swe-mode", "negative", forbidden=["swe:swe-mode", "swe:go-deeper"]),
    case("swe-mode-non-software", "swe:swe-mode", "negative", aux=["swe:go-deeper", "swe:writing"],
         forbidden=["swe:swe-mode"]),
    case("lab-mode-analyze-results", "lab:lab-mode", "natural", "route/lab/analyze-results",
         aux=["lab:go-deeper", "lab:making-plots"]),
    case("lab-mode-run-experiment", "lab:lab-mode", "natural", "route/lab/run-experiment",
         aux=["lab:go-deeper", "lab:making-plots"]),
    case("lab-mode-route-autoresearch", "lab:lab-mode", "contextual", "route/lab/autoresearch", expected_mode="run",
         aux=["lab:autoresearch", "lab:go-deeper"]),
    case("lab-mode-code-fix", "lab:lab-mode", "negative", aux=["swe:implement", *SWE_ROUTER], forbidden=["lab:lab-mode"]),
    case("lab-mode-define-metric", "lab:lab-mode", "negative", forbidden=["lab:lab-mode", "swe:go-deeper"]),
    case("making-plots-pipeline-diagram", "lab:making-plots", "negative", aux=SWE_ROUTER,
         forbidden=["lab:making-plots", "lab:lab-mode"]),
    case("making-plots-read-table", "lab:making-plots", "negative", aux=["lab:lab-mode"],
         forbidden=["lab:making-plots", "swe:go-deeper"]),
]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(root):
    plugins, skills = root / "plugins", root / "evals" / "skills"
    start = {"hooks": [{"type": "command", "command": 'cat "$CLAUDE_PLUGIN_ROOT"/hooks/session-start.md'}]}
    for plugin, names in SKILLS.items():
        write(plugins / plugin / ".claude-plugin" / "plugin.json", json.dumps({"name": plugin}))
        write(plugins / plugin / "rules" / "AGENTS.md", f"# {plugin} rules\n")
        write(plugins / plugin / "hooks" / "session-start.md", f"{plugin}: run go-deeper on a new task.\n")
        gate = {"hooks": [{"type": "command", "command": 'sh "$CLAUDE_PLUGIN_ROOT"/hooks/pr-body-gate.sh'}]}
        hooks = {"SessionStart": [start]} | ({"PreToolUse": [gate]} if plugin == "swe" else {})
        write(plugins / plugin / "hooks" / "hooks.json", json.dumps({"hooks": hooks}))
        for name in names:
            body = BODIES.get(f"{plugin}:{name}", f"# {name}\n\nThe {plugin}:{name} fixture skill.\nIts last line.\n")
            write(plugins / plugin / "skills" / name / "SKILL.md",
                  f"---\nname: {name}\ndescription: The {name} fixture skill.\n---\n\n{body}")
        for kind, files in (("playbooks", PLAYBOOKS), ("references", REFERENCES)):
            for name in files.get(plugin, []):
                write(plugins / plugin / "skills" / ROUTER[plugin] / kind / f"{name}.md",
                      f"# {name}\n\nThe {name} fixture file.\nIts last line.\n")
    write(plugins / "swe" / "hooks" / "pr-body-gate.sh", "exit 0\n")
    write(plugins / "rex-agents" / "hooks" / "hooks.json", json.dumps({"hooks": {}}))
    write(skills / "facets.json", json.dumps(facets(), indent=2) + "\n")
    for name, text in (("app.py", "VALUE = 1\n"), ("README.md", "# small-repo\n")):
        write(skills / "dataset" / "fixtures" / "small-repo" / name, text)
    write_corpus(skills / "dataset" / "dev.jsonl", CASES, source=skills / "dataset" / "dev.jsonl")
    shutil.copy2(HERE / "skill_eval.py", skills / "skill_eval.py")
    return skills / "skill_eval.py"
