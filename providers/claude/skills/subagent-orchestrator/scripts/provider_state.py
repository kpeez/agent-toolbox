#!/usr/bin/env python3

from __future__ import annotations

from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import sys


DEFAULT_PROVIDERS = [
    {
        "provider": "codex-cli",
        "rank": 1,
        "preferred_model": "gpt-5.4-med",
        "fallback_model": "gpt-5.4-high",
        "is_active": True,
        "last_failure_at": None,
        "cooldown_until": None,
        "failure_reason": None,
    },
    {
        "provider": "gemini-cli",
        "rank": 2,
        "preferred_model": "gemini-2.5-pro",
        "fallback_model": "gemini-2.5-flash",
        "is_active": True,
        "last_failure_at": None,
        "cooldown_until": None,
        "failure_reason": None,
    },
    {
        "provider": "copilot-cli",
        "rank": 3,
        "preferred_model": "claude-sonnet-4.6",
        "fallback_model": "gpt-5.4-mini",
        "is_active": True,
        "last_failure_at": None,
        "cooldown_until": None,
        "failure_reason": None,
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def default_state_path() -> Path:
    override = os.environ.get("CLAUDE_SUBAGENT_STATE_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "subagent-orchestrator" / "provider-state.json"


def build_default_state() -> dict:
    return {"providers": deepcopy(DEFAULT_PROVIDERS)}


def load_state(path: Path) -> dict:
    if not path.exists():
        return reconcile_state(build_default_state())

    payload = json.loads(path.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("providers"), list):
        raise ValueError(f"invalid provider state file: {path}")

    return reconcile_state(payload)


def reconcile_state(payload: dict) -> dict:
    by_name = {
        item["provider"]: item
        for item in payload.get("providers", [])
        if isinstance(item, dict) and "provider" in item
    }
    now = utc_now()
    providers = []

    for template in DEFAULT_PROVIDERS:
        item = deepcopy(template)
        item.update(by_name.get(template["provider"], {}))
        cooldown_until = parse_timestamp(item.get("cooldown_until"))

        if cooldown_until and cooldown_until <= now:
            item["is_active"] = True
            item["cooldown_until"] = None
            item["failure_reason"] = None
        elif cooldown_until:
            item["is_active"] = False
            item["cooldown_until"] = isoformat(cooldown_until)
        else:
            item["cooldown_until"] = None
            item["is_active"] = bool(item.get("is_active", True))

        last_failure_at = parse_timestamp(item.get("last_failure_at"))
        item["last_failure_at"] = isoformat(last_failure_at)
        providers.append(item)

    providers.sort(key=lambda item: item["rank"])
    return {"providers": providers}


def save_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def get_provider(payload: dict, provider: str) -> dict:
    for item in payload["providers"]:
        if item["provider"] == provider:
            return item
    known = ", ".join(entry["provider"] for entry in payload["providers"])
    raise ValueError(f"unknown provider {provider!r}; expected one of: {known}")


def cmd_status(args) -> int:
    state_path = Path(args.state).expanduser()
    payload = load_state(state_path)
    save_state(state_path, payload)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_rank(args) -> int:
    return cmd_status(args)


def cmd_pick(args) -> int:
    state_path = Path(args.state).expanduser()
    payload = load_state(state_path)
    save_state(state_path, payload)

    for item in payload["providers"]:
        if item["is_active"]:
            print(json.dumps(item, indent=2))
            return 0

    next_provider = min(
        payload["providers"],
        key=lambda item: item["cooldown_until"] or "9999-12-31T00:00:00Z",
    )
    print(
        json.dumps(
            {
                "provider": None,
                "reason": "no_active_provider",
                "next_provider": next_provider["provider"],
                "cooldown_until": next_provider["cooldown_until"],
            },
            indent=2,
        )
    )
    return 1


def cmd_mark_failure(args) -> int:
    state_path = Path(args.state).expanduser()
    payload = load_state(state_path)
    provider = get_provider(payload, args.provider)
    now = utc_now()
    provider["is_active"] = False
    provider["last_failure_at"] = isoformat(now)
    provider["cooldown_until"] = isoformat(now + timedelta(minutes=args.cooldown_minutes))
    provider["failure_reason"] = args.reason
    save_state(state_path, payload)
    print(json.dumps(provider, indent=2))
    return 0


def cmd_mark_success(args) -> int:
    state_path = Path(args.state).expanduser()
    payload = load_state(state_path)
    provider = get_provider(payload, args.provider)
    provider["is_active"] = True
    provider["cooldown_until"] = None
    provider["failure_reason"] = None
    save_state(state_path, payload)
    print(json.dumps(provider, indent=2))
    return 0


def build_parser() -> ArgumentParser:
    default_state = str(default_state_path())
    parser = ArgumentParser(
        description="Track Claude subagent provider ranking and temporary cooldowns."
    )
    parser.add_argument(
        "--state",
        default=default_state,
        help="Path to the provider state JSON file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show provider state.")
    status_parser.add_argument("--state", default=default_state)
    status_parser.set_defaults(func=cmd_status)

    rank_parser = subparsers.add_parser("rank", help="Show ranked provider state.")
    rank_parser.add_argument("--state", default=default_state)
    rank_parser.set_defaults(func=cmd_rank)

    pick_parser = subparsers.add_parser("pick", help="Pick the best active provider.")
    pick_parser.add_argument("--state", default=default_state)
    pick_parser.set_defaults(func=cmd_pick)

    failure_parser = subparsers.add_parser(
        "mark-failure", help="Cool down a provider after a transient failure."
    )
    failure_parser.add_argument("--state", default=default_state)
    failure_parser.add_argument("--provider", required=True)
    failure_parser.add_argument("--reason", required=True)
    failure_parser.add_argument("--cooldown-minutes", type=int, default=30)
    failure_parser.set_defaults(func=cmd_mark_failure)

    success_parser = subparsers.add_parser(
        "mark-success", help="Reactivate a provider after a successful run."
    )
    success_parser.add_argument("--state", default=default_state)
    success_parser.add_argument("--provider", required=True)
    success_parser.set_defaults(func=cmd_mark_success)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
