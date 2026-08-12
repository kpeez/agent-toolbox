"""Keep plugin skills, manifests, documentation, and references in sync."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SKILL_REFERENCE = re.compile(r"`/([a-z][a-z0-9-]+)`")
README_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|")
ALLOWED_HOST_COMMANDS = {"goal", "code-review", "clear"}
ROOT_CONTEXT_CLAIM = re.compile(
    r"\./CONTEXT\.md"
    r"|repo[- ]root[^.\n]{0,40}CONTEXT\.md"
    r"|CONTEXT\.md[^.\n]{0,40}repo[- ]root"
    r"|committed[^.\n]{0,40}CONTEXT\.md",
    re.IGNORECASE,
)


def plugin_directories() -> list[Path]:
    return sorted(path for path in (ROOT / "plugins").iterdir() if path.is_dir())


def plugin_skill_files() -> list[Path]:
    return sorted(
        skill_file
        for plugin in plugin_directories()
        for skill_file in (plugin / "skills").glob("*/SKILL.md")
    )


def all_skill_files() -> list[Path]:
    return plugin_skill_files() + sorted((ROOT / "skills").glob("*/SKILL.md"))


def frontmatter_field(skill_file: Path, field: str) -> str | None:
    """Raw frontmatter value as written (quotes included), or None."""
    text = skill_file.read_text()
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
    if match is None:
        return None
    value = re.search(rf"^{field}:\s*(.+?)\s*$", match.group(1), re.MULTILINE)
    return value.group(1).strip() if value else None


def frontmatter_name(skill_file: Path) -> str | None:
    name = frontmatter_field(skill_file, "name")
    return name.strip("\"'") if name else None


def documentation_files() -> list[Path]:
    """Committed prose agents read. CHANGELOGs record history and are exempt."""
    return [ROOT / "README.md", ROOT / "AGENTS.md"] + sorted(
        markdown
        for markdown in (ROOT / "plugins").rglob("*.md")
        if markdown.name != "CHANGELOG.md"
    )


def readme_skill_names() -> set[str]:
    lines = (ROOT / "README.md").read_text().splitlines()
    section_start = next(
        index for index, line in enumerate(lines) if line == "## Skills"
    )
    section_end = next(
        (
            index
            for index in range(section_start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return {
        match.group(1)
        for line in lines[section_start:section_end]
        if (match := README_ROW.match(line))
    }


def test_forwarder_agents_hold_only_their_providers_mcp_tools() -> None:
    """The forwarder contract is enforced by `tools`, not by its prose.

    `allowed-tools` is not a subagent frontmatter field -- an agent declaring it
    inherits every tool instead, which would let a forwarder work the task
    itself. Pin the working key on the agents whose whole purpose is delegation.
    """
    agents_dir = ROOT / "plugins" / "swe" / "agents"
    expected = {
        "opencode-explorer": "mcp__plugin_swe_opencode-explorer__delegate",
        "opencode-implementer": "mcp__plugin_swe_opencode-implementer__delegate",
        "opencode-reviewer": "mcp__plugin_swe_opencode-reviewer__delegate",
    }

    declared = {
        name: re.search(
            r"^tools:\s*(.+?)\s*$", (agents_dir / f"{name}.md").read_text(), re.M
        )
        for name in expected
    }

    assert {
        name: match.group(1) for name, match in declared.items() if match
    } == expected


def test_forwarder_mcp_tools_use_the_plugin_qualified_name() -> None:
    """A plugin-bundled tool is `mcp__plugin_<plugin>_<server>__<tool>`.

    The bare `mcp__<server>__<tool>` form resolves to nothing for a plugin
    server, and a subagent whose `tools` list resolves to nothing fails to
    launch -- so getting this wrong breaks delegation entirely rather than
    degrading it.
    """
    servers = json.loads((ROOT / "plugins" / "swe" / ".mcp.claude.json").read_text())[
        "mcpServers"
    ]
    agents_dir = ROOT / "plugins" / "swe" / "agents"

    referenced = {
        tool.rsplit("__", 1)[0].removeprefix("mcp__")
        for agent in agents_dir.glob("*.md")
        for tool in re.findall(r"mcp__[\w-]+__[\w-]+", agent.read_text())
    }

    assert referenced == {f"plugin_swe_{server}" for server in servers}


def test_swe_hooks_register_worktree_link_script() -> None:
    hooks = json.loads((ROOT / "plugins" / "swe" / "hooks" / "hooks.json").read_text())
    command = '"$CLAUDE_PLUGIN_ROOT"/hooks/symlink-worktree-shared-dirs.sh'

    subagent = hooks["hooks"]["SubagentStart"]
    assert [entry.get("matcher") for entry in subagent] == [None]
    assert [hook["command"] for entry in subagent for hook in entry["hooks"]] == [
        command
    ]

    session = hooks["hooks"]["SessionStart"]
    assert [entry["matcher"] for entry in session] == ["startup|resume"]
    assert [hook["command"] for entry in session for hook in entry["hooks"]] == [
        command
    ]

    post_tool = hooks["hooks"]["PostToolUse"]
    enter_worktree = [
        entry for entry in post_tool if entry.get("matcher") == "EnterWorktree"
    ]
    assert [hook["command"] for entry in enter_worktree for hook in entry["hooks"]] == [
        command
    ]

    script = ROOT / "plugins" / "swe" / "hooks" / "symlink-worktree-shared-dirs.sh"
    assert script.is_file()
    assert script.stat().st_mode & 0o111


def test_frontmatter_names_match_skill_directories() -> None:
    mismatches = [
        (
            skill_file.relative_to(ROOT),
            frontmatter_name(skill_file),
            skill_file.parent.name,
        )
        for skill_file in all_skill_files()
        if frontmatter_name(skill_file) != skill_file.parent.name
    ]

    assert mismatches == []


YAML_NON_STRING = re.compile(
    r"^(?:true|false|null|~|nan|[-+]?\d[\d._]*(?:[eE][-+]?\d+)?)$", re.IGNORECASE
)


def parse_contract_problem(skill_file: Path) -> str | None:
    """First skills.sh parse-contract violation, or None.

    The skills.sh CLI skips any SKILL.md whose `name` or `description` is
    missing or parses as a YAML non-string (number, boolean, null), silently
    dropping the skill from the picker. Quoted values are YAML strings and
    pass; block scalars (`|`) are strings too and do not match the regex."""
    for field in ("name", "description"):
        value = frontmatter_field(skill_file, field)
        if not value:
            return f"missing {field}"
        if not value.startswith(("'", '"')) and YAML_NON_STRING.match(value):
            return f"{field} is a YAML non-string ({value})"
    return None


def test_skills_meet_the_skills_sh_parse_contract() -> None:
    """The skills.sh installer (npx skills add) skips any SKILL.md without
    string `name` and `description` frontmatter, silently dropping the skill
    from the picker. Every skill must satisfy that contract or the npx install
    path loses it."""
    problems = [
        (skill_file.relative_to(ROOT), problem)
        for skill_file in all_skill_files()
        if (problem := parse_contract_problem(skill_file))
    ]

    assert problems == []


def test_plugin_manifest_versions_match() -> None:
    mismatches: list[tuple[str, str | None, str | None]] = []

    for plugin in plugin_directories():
        claude_manifest = plugin / ".claude-plugin" / "plugin.json"
        codex_manifest = plugin / ".codex-plugin" / "plugin.json"
        claude_version = (
            json.loads(claude_manifest.read_text()).get("version")
            if claude_manifest.is_file()
            else None
        )
        codex_version = (
            json.loads(codex_manifest.read_text()).get("version")
            if codex_manifest.is_file()
            else None
        )
        if claude_version != codex_version or claude_version is None:
            mismatches.append((plugin.name, claude_version, codex_version))

    assert mismatches == []


def test_lab_owns_the_complete_research_workflow_surface() -> None:
    """A missing or duplicated entry point silently changes installed capability."""
    skill_names = {
        plugin.name: {
            skill_file.parent.name
            for skill_file in (plugin / "skills").glob("*/SKILL.md")
        }
        for plugin in plugin_directories()
    }

    assert skill_names["lab"] == {
        "research",
        "deep-research",
        "autoresearch",
        "data-viz",
    }
    assert "research" not in skill_names["swe"]


def test_lab_manifests_share_installation_metadata() -> None:
    """Provider installs must describe and version the same Lab product."""
    lab = ROOT / "plugins" / "lab"
    claude = json.loads((lab / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((lab / ".codex-plugin" / "plugin.json").read_text())

    shared_fields = (
        "name",
        "description",
        "version",
        "homepage",
        "repository",
        "license",
        "keywords",
    )
    assert {field: claude[field] for field in shared_fields} == {
        field: codex[field] for field in shared_fields
    }
    assert codex["skills"] == "./skills/"


def test_autoresearch_default_artifact_root_is_gitignored() -> None:
    """Private run artifacts must not become publishable repository changes."""
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", ".autoresearch/example/results.tsv"],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0


def test_readme_skills_table_matches_plugin_skills() -> None:
    expected = {skill_file.parent.name for skill_file in plugin_skill_files()}

    assert readme_skill_names() == expected


def test_backtick_skill_references_are_live() -> None:
    known_skills = {
        skill_file.parent.name for skill_file in all_skill_files()
    } | ALLOWED_HOST_COMMANDS
    targets = [ROOT / "README.md", ROOT / "AGENTS.md"]
    targets.extend(sorted((ROOT / "plugins").rglob("*.md")))
    dead_references = [
        (markdown.relative_to(ROOT), reference)
        for markdown in targets
        for reference in sorted(set(SKILL_REFERENCE.findall(markdown.read_text())))
        if reference not in known_skills
    ]

    assert dead_references == []


def test_context_glossary_is_not_in_the_repo() -> None:
    assert not (ROOT / "CONTEXT.md").exists()


def test_documentation_places_context_glossary_under_docs_agents() -> None:
    stale_claims = [
        (markdown.relative_to(ROOT), match.group(0))
        for markdown in documentation_files()
        for match in ROOT_CONTEXT_CLAIM.finditer(markdown.read_text())
    ]

    assert stale_claims == []


SWE_PLUGIN = ROOT / "plugins" / "swe"
SWE_MCP = SWE_PLUGIN / ".mcp.json"
SWE_CLAUDE_MCP = SWE_PLUGIN / ".mcp.claude.json"
OPENCODE_MODEL = re.compile(r"opencode-go/[\w.-]+")


def opencode_servers() -> dict[str, list[str]]:
    servers = json.loads(SWE_MCP.read_text())["mcpServers"]
    return {
        name: config["args"]
        for name, config in servers.items()
        if name.startswith("opencode-")
    }


def pinned_models() -> dict[str, str]:
    """server -> the model its `--model` flag pins, the one operative source."""
    return {
        name: args[args.index("--model") + 1]
        for name, args in opencode_servers().items()
    }


def normalized_opencode_contract(
    config: dict[str, Any], *, timeout_field: str, timeout_scale: int
) -> dict[str, object]:
    args = list(config["args"])
    bridge = str(args[0])
    if bridge in {
        "${CLAUDE_PLUGIN_ROOT}/mcp/acp_bridge.py",
        "mcp/acp_bridge.py",
    }:
        args[0] = "<plugin-root>/mcp/acp_bridge.py"

    return {
        "command": config["command"],
        "args": args,
        "timeout_ms": config[timeout_field] * timeout_scale,
    }


def test_codex_and_claude_package_the_same_opencode_role_contracts() -> None:
    """A host-specific transport edit must not silently change provider policy."""
    claude_manifest = json.loads(
        (SWE_PLUGIN / ".claude-plugin" / "plugin.json").read_text()
    )
    codex_manifest = json.loads(
        (SWE_PLUGIN / ".codex-plugin" / "plugin.json").read_text()
    )
    assert claude_manifest["mcpServers"] == "./.mcp.claude.json"
    assert codex_manifest["mcpServers"] == "./.mcp.json"

    claude_servers = json.loads(SWE_CLAUDE_MCP.read_text())["mcpServers"]
    codex_servers = json.loads(SWE_MCP.read_text())["mcpServers"]
    role_names = {
        "opencode-explorer",
        "opencode-implementer",
        "opencode-reviewer",
    }

    assert set(claude_servers) == role_names
    assert set(codex_servers) == role_names
    for name in role_names:
        assert codex_servers[name]["cwd"] == "."
        assert "${CLAUDE_PLUGIN_ROOT}" not in json.dumps(codex_servers[name])
        assert normalized_opencode_contract(
            claude_servers[name], timeout_field="timeout", timeout_scale=1
        ) == normalized_opencode_contract(
            codex_servers[name], timeout_field="tool_timeout_sec", timeout_scale=1000
        )


def test_opencode_runs_through_the_generic_acp_bridge() -> None:
    """Not a parallel delegation path: the same bridge Copilot proved out, with
    the agent command as its argv, is what OpenCode arrives through."""
    servers = opencode_servers()
    assert set(servers) == {
        "opencode-explorer",
        "opencode-implementer",
        "opencode-reviewer",
    }

    for name, args in servers.items():
        assert args[0].endswith("mcp/acp_bridge.py"), name
        assert args[-2:] == ["opencode", "acp"], name


def test_every_opencode_server_pins_its_open_code_session_policy() -> None:
    """Each role pins the OpenCode session policy required by its contract."""
    for name, args in opencode_servers().items():
        if name == "opencode-reviewer":
            assert args[args.index("--mode") + 1] == "review", name
        elif name == "opencode-implementer":
            assert args[args.index("--write-mode") + 1] == "build", name
        else:
            assert args[args.index("--read-only-mode") + 1] == "plan", name


def test_opencode_role_models_are_the_documented_policy() -> None:
    assert pinned_models() == {
        "opencode-explorer": "opencode-go/deepseek-v4-flash",
        "opencode-implementer": "opencode-go/gpt-5.6-luna",
        "opencode-reviewer": "opencode-go/deepseek-v4-pro",
    }


def test_the_reviewer_never_shares_the_implementers_model() -> None:
    """Cross-model review is why review is not simply routed to the coding model."""
    models = pinned_models()

    assert models["opencode-implementer"] != models["opencode-reviewer"]


def test_model_ids_live_only_in_the_mcp_manifest_and_agree_with_it() -> None:
    """One operative source. Prose may name a model, but only its own, so
    replacing a model is a one-line edit that the docs cannot silently outlive."""
    models = pinned_models()
    agents_dir = ROOT / "plugins" / "swe" / "agents"

    for server, model in models.items():
        agent = agents_dir / f"{server}.md"
        assert set(OPENCODE_MODEL.findall(agent.read_text())) == {model}, agent.name

    # Skills mostly route by role; the one exception (start-loop's model-policy
    # table, checked below for its bare names) still never spells out the
    # qualified `opencode-go/...` id.
    unpinned_sources = sorted((ROOT / "plugins" / "swe" / "skills").glob("*/SKILL.md"))
    offenders = [
        (path.name, match)
        for path in unpinned_sources
        for match in OPENCODE_MODEL.findall(path.read_text())
    ]
    assert offenders == []

    # Documentation may list the policy, but only models the manifest pins.
    documented = set(
        OPENCODE_MODEL.findall((ROOT / "plugins" / "swe" / "README.md").read_text())
    )
    assert documented <= set(models.values())


# Shape of a bare (unprefixed) OpenCode model id, as the manifest's own pinned
# ids demonstrate: `<family>-<version>-<tier>` (deepseek-v4-flash,
# deepseek-v4-pro), or a `gpt-`/`deepseek-` id of any shape. Broad enough to
# catch a bare model name docs forgot to update, without matching ordinary
# prose words.
BARE_MODEL_SHAPE_RE = re.compile(
    r"[a-z]+-[a-z0-9.]+-(?:pro|flash|luna|nova)|gpt-\d[\w.-]*|deepseek-[\w.-]+"
)


def test_bare_opencode_model_names_agree_with_the_mcp_manifest() -> None:
    """The manifest's pinned models are the one operative source; expected bare
    names are derived FROM it, not the other way around, so repinning any one
    model in `.mcp.json` must fail this test until the docs catch up. Each
    pinned bare name must show up in start-loop's model table, and no other
    model-shaped token may appear unpinned there or in the README's Model
    policy prose."""
    models = pinned_models()
    bare_models = {model.split("/", 1)[1] for model in models.values()}

    start_loop = (
        ROOT / "plugins" / "swe" / "skills" / "start-loop" / "SKILL.md"
    ).read_text()
    for bare_name in bare_models:
        assert bare_name in start_loop, (
            f"start-loop's model table is missing pinned model {bare_name!r}"
        )
    found_in_start_loop = set(BARE_MODEL_SHAPE_RE.findall(start_loop))
    assert found_in_start_loop <= bare_models, (
        "start-loop names a model-shaped token not pinned in .mcp.json: "
        f"{found_in_start_loop - bare_models}"
    )

    # The README's own Model policy prose only, not any qualified `opencode-go/...`
    # id named elsewhere in the file (e.g. the "Delegating to another provider"
    # section), so a stale bare name outside that section can't hide.
    readme = (ROOT / "plugins" / "swe" / "README.md").read_text()
    policy_match = re.search(r"### Model policy\n(.*?)\n## ", readme, re.DOTALL)
    assert policy_match is not None, "README has no Model policy section"
    policy_prose = policy_match.group(1)

    found_in_policy = set(BARE_MODEL_SHAPE_RE.findall(policy_prose))
    assert found_in_policy, "README's Model policy prose names no bare OpenCode model"
    assert found_in_policy <= bare_models, (
        "README's Model policy prose names a model-shaped token not pinned in "
        f".mcp.json: {found_in_policy - bare_models}"
    )


def test_dropping_copilot_left_no_dangling_references() -> None:
    """A forwarder named in prose but absent from .mcp.json is a dead route."""
    live = [ROOT / "README.md", ROOT / "AGENTS.md", SWE_MCP] + [
        path
        for path in (ROOT / "plugins" / "swe").rglob("*.md")
        if path.name != "CHANGELOG.md"
    ]
    offenders = [
        path.relative_to(ROOT)
        for path in live
        if "copilot-delegator" in path.read_text()
        or "plugin_swe_copilot" in path.read_text()
    ]

    assert offenders == []


def test_no_agent_declares_the_ignored_allowed_tools_key() -> None:
    """`allowed-tools` is a slash-command field; a subagent declaring it is not
    restricted at all, it inherits everything. Prose calling an agent read-only
    while it silently holds Write and Bash is the failure this prevents."""
    agents_dir = ROOT / "plugins" / "swe" / "agents"
    offenders = [
        path.name
        for path in sorted(agents_dir.glob("*.md"))
        if re.search(r"^allowed-tools:", path.read_text(), re.M)
    ]

    assert offenders == []


def test_the_planner_reaches_the_explorer_without_nesting() -> None:
    """A subagent cannot spawn a subagent, so the planner calls the available
    explorer MCP delegate directly. It declares no `tools:` list on purpose: /to-issues
    resolves the tracker per repo at runtime, and a static list would cut off
    whichever of Linear's MCP tools, `gh`, or plain files it picks."""
    planner = (ROOT / "plugins" / "swe" / "agents" / "planner.md").read_text()

    assert re.search(r"available OpenCode\s+explorer delegate tool", planner)
    assert re.search(r"^tools:", planner, re.M) is None


def test_every_opencode_forwarder_has_a_caller() -> None:
    """A forwarder nothing dispatches is a pinned model, a documented rationale
    and a spawned bridge process serving no call site. Reachability is the
    property worth pinning, so either entry point counts: the subagent name for
    a caller that can nest, the MCP tool for one that cannot."""
    plugin = ROOT / "plugins" / "swe"
    callers = sorted((plugin / "skills").glob("*/SKILL.md"))
    callers += sorted(
        path
        for path in (plugin / "agents").glob("*.md")
        if not path.name.startswith("opencode-")
    )
    text = "\n".join(path.read_text() for path in callers)

    uncalled = [
        name
        for name in opencode_servers()
        if f"swe:{name}" not in text
        and f"mcp__plugin_swe_{name}__delegate" not in text
        and f"mcp__{name.replace('-', '_')}__delegate" not in text
    ]

    assert uncalled == []


def test_codex_manual_workflow_reaches_every_native_opencode_delegate() -> None:
    """Codex has no forwarder subagents, so its manual fallback must call each
    plugin-delivered delegate directly and preserve the role's write boundary."""
    skills = ROOT / "plugins" / "swe" / "skills"
    implement = (skills / "implement" / "SKILL.md").read_text()
    to_issues = (skills / "to-issues" / "SKILL.md").read_text()

    assert "Manual fallback (no forwarder subagents)" in implement
    assert "mcp__opencode_explorer__delegate" in to_issues

    for tool, mode in (
        ("mcp__opencode_explorer__delegate", 'mode: "read-only"'),
        ("mcp__opencode_implementer__delegate", 'mode: "write"'),
        ("mcp__opencode_reviewer__delegate", 'mode: "review"'),
    ):
        assert tool in implement, f"{tool} missing from implement's manual fallback"
        assert mode in implement, f"{mode} missing from implement's manual fallback"
    assert "cwd" in implement


def test_start_loop_is_the_lead_orchestrated_run_procedure() -> None:
    """start-loop dispatches implementers and a reviewer directly and runs
    gates itself — no Workflow tool launch, no planner or plumbing agents."""
    start_loop = (
        ROOT / "plugins" / "swe" / "skills" / "start-loop" / "SKILL.md"
    ).read_text()

    for present in (
        "fresh session",
        "approved: true",
        "the lead never reads code",
        "verification gates",
        "git merge --no-ff",
        "Model policy",
        "Manual fallback (no forwarder subagents)",
    ):
        assert present.lower() in start_loop.lower(), f"missing: {present}"

    for absent in ("scriptPath", "workableCmd", "swe:planner", "containerId"):
        assert absent not in start_loop, f"should be gone: {absent}"
