"""A scriptable ACP agent, so bridge tests need no provider CLI or network.

The prompt text is a JSON directive describing the tool calls the agent should
attempt, which lets one fixture stand in for every permission scenario:

    {"attempts": [{"kind": "edit", "paths": ["/tmp/x"]}], "reply": "done"}

Each attempt triggers a real `session/request_permission` round trip, so the
bridge's policy is exercised over the wire rather than called directly.

Command-line flags shape what the agent advertises, so one fixture also stands
in for the two ACP dialects the bridge has to speak: a bare agent that exposes
nothing but `session/set_model`, and an OpenCode-shaped one that answers
`session/new` with `configOptions` and validates every selection.

    --models a,b        session/set_model rejects anything else
    --efforts low,high  advertise an `effort` config option (first is current)
    --modes build,plan  advertise a `mode` config option (first is current)

`{"echo_config": true}` in the directive appends the selections the agent
actually ended up with, which is how a test proves the bridge sent them -- and
sent the model before the effort that depends on it.
"""

from __future__ import annotations

import json
import sys
from typing import Any

SESSION_ID = "fake-session-1"

# What this run advertises and what has been selected on it. A module-level
# dict is enough: the fixture serves exactly one session.
CONFIG: dict[str, Any] = {"model": None, "order": []}
ADVERTISED: dict[str, list[str]] = {}
KNOWN_MODELS: list[str] = []


def config_options() -> list[dict[str, Any]]:
    return [
        {
            "id": config_id,
            "name": config_id,
            "type": "select",
            "currentValue": CONFIG.get(config_id, values[0]),
            "options": [{"value": value, "name": value} for value in values],
        }
        for config_id, values in ADVERTISED.items()
    ]


def set_config_option(params: dict[str, Any]) -> dict[str, Any] | str:
    """Apply one selection, or return the error text for an illegal one."""
    config_id = params.get("configId")
    value = params.get("value")
    if config_id not in ADVERTISED:
        return f"unknown config option: {config_id}"
    if value not in ADVERTISED[config_id]:
        return f"{config_id} not found: {value}"
    CONFIG[config_id] = value
    CONFIG["order"].append(f"{config_id}={value}")
    return {"configOptions": config_options()}


def send(frame: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(frame) + "\n")
    sys.stdout.flush()


def read_frame() -> dict[str, Any] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    return json.loads(line) if line else {}


def request_permission(request_id: int, attempt: dict[str, Any]) -> dict[str, Any]:
    """Ask the client for permission and block until it answers."""
    send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "session/request_permission",
            "params": {
                "sessionId": SESSION_ID,
                "toolCall": {
                    "toolCallId": f"call-{request_id}",
                    "title": attempt.get("title", "Fake call"),
                    "kind": attempt.get("kind", "other"),
                    "status": "pending",
                    "locations": [{"path": path} for path in attempt.get("paths", [])],
                },
                "options": attempt.get(
                    "options",
                    [
                        {"optionId": "allow_once", "kind": "allow_once", "name": "Allow once"},
                        {"optionId": "allow_always", "kind": "allow_always", "name": "Always"},
                        {"optionId": "reject_once", "kind": "reject_once", "name": "Deny"},
                    ],
                ),
            },
        }
    )
    while True:
        frame = read_frame()
        if frame is None:
            raise SystemExit(0)
        if frame.get("id") == request_id:
            return frame.get("result", {})


def handle_prompt(message: dict[str, Any], permission_id: list[int]) -> None:
    text = message["params"]["prompt"][0]["text"]
    directive = json.loads(text)
    granted: list[str] = []

    for attempt in directive.get("attempts", []):
        send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": SESSION_ID,
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": f"call-{permission_id[0]}",
                        "title": attempt.get("title", "Fake call"),
                        "kind": attempt.get("kind", "other"),
                        "status": "pending",
                    },
                },
            }
        )
        outcome = request_permission(permission_id[0], attempt).get("outcome", {})
        permission_id[0] += 1
        if outcome.get("outcome") == "selected" and "allow" in outcome.get("optionId", ""):
            granted.append(attempt.get("kind", "other"))

    reply = directive.get("reply", "")
    if directive.get("echo_granted"):
        reply = f"{reply}granted={','.join(granted)}"
    if directive.get("echo_config"):
        reply = f"{reply}config={'|'.join(CONFIG['order'])}"
    if reply:
        send(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": SESSION_ID,
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": reply},
                    },
                },
            }
        )

    send(
        {
            "jsonrpc": "2.0",
            "id": message["id"],
            "result": {
                "stopReason": directive.get("stopReason", "end_turn"),
                "usage": {"totalTokens": 42},
            },
        }
    )


def error(message_id: Any, text: str) -> dict[str, Any]:
    """An ACP agent rejects an illegal selection; it does not silently ignore it."""
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": -32602, "message": f"Invalid params: {text}"},
    }


def main() -> int:
    argv = sys.argv[1:]
    for index in range(0, len(argv) - 1, 2):
        flag, value = argv[index], argv[index + 1]
        if flag == "--models":
            KNOWN_MODELS.extend(value.split(","))
        elif flag in ("--efforts", "--modes"):
            ADVERTISED[flag.removeprefix("--").rstrip("s")] = value.split(",")

    permission_id = [0]
    while True:
        message = read_frame()
        if message is None:
            return 0
        method = message.get("method")

        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {
                        "protocolVersion": 1,
                        "agentCapabilities": {"loadSession": True},
                        "agentInfo": {"name": "FakeAgent", "version": "0.0.1"},
                    },
                }
            )
        elif method == "session/new":
            result: dict[str, Any] = {"sessionId": SESSION_ID}
            if ADVERTISED:
                result["configOptions"] = config_options()
            send({"jsonrpc": "2.0", "id": message["id"], "result": result})
        elif method == "session/set_model":
            model = message["params"].get("modelId")
            if KNOWN_MODELS and model not in KNOWN_MODELS:
                send(error(message["id"], f"model not found: {model}"))
                continue
            CONFIG["model"] = model
            CONFIG["order"].append(f"model={model}")
            send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        elif method == "session/set_config_option":
            applied = set_config_option(message["params"])
            if isinstance(applied, str):
                send(error(message["id"], applied))
                continue
            send({"jsonrpc": "2.0", "id": message["id"], "result": applied})
        elif method == "session/prompt":
            handle_prompt(message, permission_id)
        elif "id" in message:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "error": {"code": -32601, "message": f"no method {method}"},
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
