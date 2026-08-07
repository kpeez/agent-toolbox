"""A scriptable ACP agent, so bridge tests need no provider CLI or network.

The prompt text is a JSON directive describing the tool calls the agent should
attempt, which lets one fixture stand in for every permission scenario:

    {"attempts": [{"kind": "edit", "paths": ["/tmp/x"]}], "reply": "done"}

Each attempt triggers a real `session/request_permission` round trip, so the
bridge's policy is exercised over the wire rather than called directly.
"""

from __future__ import annotations

import json
import sys
from typing import Any

SESSION_ID = "fake-session-1"


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


def main() -> int:
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
            send({"jsonrpc": "2.0", "id": message["id"], "result": {"sessionId": SESSION_ID}})
        elif method == "session/set_model":
            send({"jsonrpc": "2.0", "id": message["id"], "result": {}})
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
