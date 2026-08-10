"""Keep plugin skills, manifests, documentation, and references in sync."""

from __future__ import annotations

import json
import re
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


SWE_LOOP = ROOT / "plugins" / "swe" / "workflows" / "swe-loop.js"


def test_swe_loop_routes_worker_roles_through_the_roles_map() -> None:
    text = SWE_LOOP.read_text()

    routable = re.search(r"ROUTABLE_ROLES = \[([^\]]+)\]", text)
    assert routable is not None
    declared = set(re.findall(r"'([a-z-]+)'", routable.group(1)))
    routed = set(re.findall(r"agentTypeFor\('([a-z-]+)'\)", text))
    assert routed == declared == {"planner", "implementer", "reviewer", "publisher"}

    # A hardcoded agentType in any quoting style would bypass the roles arg.
    assert re.findall(r"agentType:\s*['\"`]swe:", text) == []


def delegators_block() -> str:
    """The DELEGATORS literal, brace-matched -- one provider's value is a map."""
    text = SWE_LOOP.read_text()
    start = text.index("const DELEGATORS = {")
    depth = 0
    for index in range(text.index("{", start), len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[start : index + 1]
    raise AssertionError("swe-loop.js no longer declares a closed DELEGATORS map")


def test_every_routable_provider_has_a_forwarder_agent() -> None:
    """A provider the loop accepts but cannot dispatch fails only at run time."""
    agents_dir = ROOT / "plugins" / "swe" / "agents"
    forwarders = set(re.findall(r"'(swe:[a-z0-9-]+)'", delegators_block()))

    assert forwarders == {
        "swe:opencode-implementer",
        "swe:opencode-reviewer",
    }
    missing = [
        agent_type
        for agent_type in forwarders
        if not (agents_dir / f"{agent_type.removeprefix('swe:')}.md").is_file()
    ]

    assert missing == []


def test_the_default_routing_offloads_exactly_implementer_and_reviewer() -> None:
    """These defaults are the run's cost policy: widening them silently is the
    change this guards, the same way the fix-round ceilings are guarded."""
    declaration = re.search(
        r"DEFAULT_ROLE_PROVIDERS = \{([^}]*)\}", SWE_LOOP.read_text()
    )
    assert declaration is not None

    assert dict(re.findall(r"(\w+): '([a-z]+)'", declaration.group(1))) == {
        "implementer": "opencode",
        "reviewer": "opencode",
    }


def agent_calls(text: str) -> list[str]:
    """Every `agent(...)` call in the conductor, paren-matched to its close."""
    calls = []
    for match in re.finditer(r"\bagent\(", text):
        depth = 0
        for index in range(match.end() - 1, len(text)):
            depth += {"(": 1, ")": -1}.get(text[index], 0)
            if depth == 0:
                calls.append(text[match.start() : index + 1])
                break
    return [call for call in calls if "label:" in call]


def test_every_conductor_agent_call_pins_its_model() -> None:
    """A call with neither agentType nor model inherits whatever model the host
    session is running, so the same run settles on Fable one day and Sonnet the
    next. Every call must name one or the other."""
    calls = agent_calls(SWE_LOOP.read_text())
    assert len(calls) >= 8, f"only found {len(calls)} agent call sites"

    unpinned = [
        call.split("label:", 1)[1].splitlines()[0].strip()
        for call in calls
        if "agentType:" not in call and "model:" not in call
    ]

    assert unpinned == []


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
    servers = json.loads(
        (ROOT / "plugins" / "swe" / ".mcp.claude.json").read_text()
    )["mcpServers"]
    agents_dir = ROOT / "plugins" / "swe" / "agents"

    referenced = {
        tool.rsplit("__", 1)[0].removeprefix("mcp__")
        for agent in agents_dir.glob("*.md")
        for tool in re.findall(r"mcp__[\w-]+__[\w-]+", agent.read_text())
    }

    assert referenced == {f"plugin_swe_{server}" for server in servers}


def test_swe_loop_stays_tracker_agnostic() -> None:
    # Tracker mechanics live in the to-issues tracker references
    # (references/issue-tracker-*.md); the loop's runner skill and conductor
    # dispatch through them at runtime and never name a tracker themselves.
    start_loop = ROOT / "plugins" / "swe" / "skills" / "start-loop" / "SKILL.md"
    offenders = [
        (path.name, match)
        for path in (SWE_LOOP, start_loop)
        for match in re.findall(r"linear|github", path.read_text(), re.IGNORECASE)
    ]

    assert offenders == []


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


def test_every_opencode_server_enforces_read_only_through_opencodes_own_mode() -> None:
    """OpenCode auto-approves in-workspace edits without asking the bridge, so a
    server that forgets this flag serves read-only delegations that can write."""
    for name, args in opencode_servers().items():
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

    # The conductor and the skills route by role and never name a model.
    unpinned_sources = [SWE_LOOP] + sorted(
        (ROOT / "plugins" / "swe" / "skills").glob("*/SKILL.md")
    )
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


def test_dropping_copilot_left_no_dangling_references() -> None:
    """A forwarder named in prose but absent from .mcp.json is a dead route."""
    live = [ROOT / "README.md", ROOT / "AGENTS.md", SWE_MCP, SWE_LOOP] + [
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
    """A subagent cannot spawn a subagent, so the planner calls the forwarder's
    MCP tool directly. It declares no `tools:` list on purpose: /to-issues
    resolves the tracker per repo at runtime, and a static list would cut off
    whichever of Linear's MCP tools, `gh`, or plain files it picks."""
    planner = (ROOT / "plugins" / "swe" / "agents" / "planner.md").read_text()

    assert "mcp__plugin_swe_opencode-explorer__delegate" in planner
    assert re.search(r"^tools:", planner, re.M) is None


def test_every_opencode_forwarder_has_a_caller() -> None:
    """A forwarder nothing dispatches is a pinned model, a documented rationale
    and a spawned bridge process serving no call site. Reachability is the
    property worth pinning, so either entry point counts: the subagent name for
    a caller that can nest, the MCP tool for one that cannot."""
    plugin = ROOT / "plugins" / "swe"
    callers = [plugin / "workflows" / "swe-loop.js"]
    callers += sorted((plugin / "skills").glob("*/SKILL.md"))
    callers += sorted(
        path
        for path in (plugin / "agents").glob("*.md")
        if not path.name.startswith("opencode-")
    )
    text = "\n".join(path.read_text() for path in callers)

    uncalled = [
        name
        for name in opencode_servers()
        if f"swe:{name}" not in text and f"mcp__plugin_swe_{name}__delegate" not in text
    ]

    assert uncalled == []


def test_codex_manual_workflow_reaches_every_native_opencode_delegate() -> None:
    """Codex has no Workflow tool or Claude forwarder agents, so its manual
    conductor must call each plugin-delivered delegate directly and preserve
    the role's write boundary."""
    skills = ROOT / "plugins" / "swe" / "skills"
    implement = (skills / "implement" / "SKILL.md").read_text()
    to_issues = (skills / "to-issues" / "SKILL.md").read_text()
    start_loop = (skills / "start-loop" / "SKILL.md").read_text()

    assert "mcp__plugin_swe_opencode-explorer__delegate" in implement
    assert "mcp__plugin_swe_opencode-implementer__delegate" in implement
    assert "mcp__plugin_swe_opencode-reviewer__delegate" in implement
    assert "mcp__plugin_swe_opencode-explorer__delegate" in to_issues
    assert 'mode: "write"' in implement
    assert implement.count('mode: "read-only"') >= 2
    assert "cwd" in implement
    assert "manual orchestration in `/implement`" in start_loop

    assert "swe:opencode-explorer" in implement
    assert "swe:opencode-implementer" in implement
    assert "swe:opencode-reviewer" in implement
    assert "silent fallback" in implement
