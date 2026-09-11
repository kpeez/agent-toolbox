#!/usr/bin/env python3
"""Fake ACP v1 agent mimicking `opencode acp` for offline bridge tests.

Speaks the ACP v1 JSON-RPC newline protocol from the official spec
(https://agentclientprotocol.com/). Every prompt is its own turn with a fresh
cancel event and an immutable request id captured when the prompt arrives, so a
late cancel from an earlier turn can never reach a later one.

Behavior is selected by a marker in the prompt text:

  [[long]]           3 x 10000-char chunks (A/B/C), then end_turn
  [[slow]]           waits ~3s, cancellable via session/cancel
  [[hold]]           waits ~15s, cancellable via session/cancel
  [[permission]]     sends session/request_permission and reports the outcome
  [[stall-cancel]]   ignores session/cancel for ~20s, then end_turn
  [[crash]]          exits the process mid-prompt (exit code 9)
  [[policy]]         echoes selected, nonsecret effective env-config fields
  anything else      echoes "echo:<text> | session=<sid> | cwd=<cwd> |
                     model=<model>" so session/cwd isolation is observable

`session/close` for a session whose current turn is still unresolved is
rejected, so the bridge must keep the slot. Stdlib only; no network; never
launches further processes.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

WRITE_LOCK = threading.Lock()
LOCK = threading.Lock()
SESSION_SEQ = 0
TURN_SEQ = 0
SESSIONS = {}
PERMISSION_WAITERS = {}

# The model option carries a group, so grouped values (not just flat options)
# are exercised by the bridge's model selection.
MODEL_OPTIONS = [
    {"id": "model", "name": "Model", "category": "model", "type": "select",
     "currentValue": "fake/default",
     "options": [
         {"value": "fake/default", "name": "Fake Default"},
         {"name": "Alternates", "options": [
             {"value": "fake/alt", "name": "Fake Alternate"},
             {"value": "fake/grouped", "name": "Fake Grouped"},
         ]},
     ]},
    {"id": "mode", "name": "Session Mode", "category": "mode", "type": "select",
     "currentValue": "build",
     "options": [{"value": "build", "name": "Build"}]},
]

# Only these nonsecret config keys are ever reported back; credentials and the
# rest of the child environment are never printed.
POLICY_KEYS = ("permission", "tools", "share", "mode", "model",
               "default_agent", "agent")


def write_message(message):
    line = json.dumps(message, separators=(",", ":"))
    with WRITE_LOCK:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def reply(request_id, result):
    write_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def reply_error(request_id, code, message):
    write_message({"jsonrpc": "2.0", "id": request_id,
                   "error": {"code": code, "message": message}})


def send_chunk(session_id, text):
    write_message({"jsonrpc": "2.0", "method": "session/update",
                   "params": {"sessionId": session_id, "update": {
                       "sessionUpdate": "agent_message_chunk",
                       "content": {"type": "text", "text": text}}}})


def collect_values(options):
    """Flatten a select option's values, recursing into groups."""
    values = []
    for entry in options or []:
        if not isinstance(entry, dict):
            continue
        value = entry.get("value")
        if isinstance(value, str):
            values.append(value)
        values.extend(collect_values(entry.get("options")))
    return values


def describe_options(model_value):
    options = json.loads(json.dumps(MODEL_OPTIONS))
    for option in options:
        if option["id"] == "model":
            option["currentValue"] = model_value
    return options


def policy_report():
    """Selected effective policy fields read from the injected child config."""
    config = {}
    raw = os.environ.get("OPENCODE_CONFIG_CONTENT")
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            config = parsed
    return {key: config[key] for key in POLICY_KEYS if key in config}


def handle_initialize(request_id):
    reply(request_id, {
        "protocolVersion": 1,
        "agentInfo": {"name": "fake-opencode", "version": "0.0.0"},
        "agentCapabilities": {
            "loadSession": False,
            "promptCapabilities": {"text": True},
            "sessionCapabilities": {
                "close": {}, "fork": {}, "list": {}, "resume": {},
            },
        },
        "authMethods": [],
    })


def handle_session_new(request_id, params):
    global SESSION_SEQ
    with LOCK:
        SESSION_SEQ += 1
        session_id = "sess-{}".format(SESSION_SEQ)
        SESSIONS[session_id] = {
            "session_id": session_id,
            "cwd": params.get("cwd", ""),
            "model": "fake/default",
            "turn": None,
        }
    reply(request_id,
          {"sessionId": session_id, "configOptions": describe_options("fake/default")})


def handle_set_config_option(request_id, params):
    with LOCK:
        state = SESSIONS.get(params.get("sessionId"))
    if state is None:
        reply_error(request_id, -32000,
                    "unknown session {!r}".format(params.get("sessionId")))
        return
    config_id = params.get("configId")
    value = params.get("value")
    option = next((o for o in MODEL_OPTIONS if o["id"] == config_id), None)
    if option is None:
        reply_error(request_id, -32000, "unknown configId {!r}".format(config_id))
        return
    offered = collect_values(option.get("options"))
    if value not in offered:
        reply_error(request_id, -32000,
                    "value {!r} not offered for {!r}: {}".format(
                        value, config_id, offered))
        return
    if config_id == "model":
        state["model"] = value
    reply(request_id, {"configOptions": describe_options(state["model"])})


def handle_close(request_id, params):
    session_id = params.get("sessionId")
    with LOCK:
        state = SESSIONS.get(session_id)
        turn = state.get("turn") if state else None
    if turn is not None and not turn["done"]:
        reply_error(request_id, -32000,
                    "session {!r} still has an unresolved prompt".format(session_id))
        return
    with LOCK:
        SESSIONS.pop(session_id, None)
    reply(request_id, {})


def handle_prompt(request_id, params):
    global TURN_SEQ
    session_id = params.get("sessionId")
    with LOCK:
        state = SESSIONS.get(session_id)
    if state is None:
        reply_error(request_id, -32000, "unknown session {!r}".format(session_id))
        return
    text = "".join(block.get("text", "") for block in params.get("prompt", [])
                   if isinstance(block, dict))
    with LOCK:
        TURN_SEQ += 1
        turn = {
            "request_id": request_id,
            "cancelled": threading.Event(),
            "text": text,
            "done": False,
            "seq": TURN_SEQ,
        }
        state["turn"] = turn
    threading.Thread(target=run_turn, args=(state, turn), daemon=True).start()


def handle_cancel(params):
    with LOCK:
        state = SESSIONS.get(params.get("sessionId"))
        turn = state.get("turn") if state else None
    if turn is not None and not turn["done"]:
        turn["cancelled"].set()


def send_permission_request(session_id, request_id):
    write_message({
        "jsonrpc": "2.0", "id": request_id,
        "method": "session/request_permission",
        "params": {
            "sessionId": session_id,
            "toolCall": {"toolCallId": "call-1", "title": "Fake risky tool",
                         "kind": "execute", "status": "pending"},
            "options": [
                {"optionId": "allow-once", "name": "Allow once", "kind": "allow_once"},
                {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"},
            ],
        },
    })


def run_permission(session_id, turn):
    request_id = "perm-{}-{}".format(session_id, turn["seq"])
    waiter = {"event": threading.Event(), "result": None}
    with LOCK:
        PERMISSION_WAITERS[request_id] = waiter
    send_permission_request(session_id, request_id)
    waiter["event"].wait(10.0)
    response = waiter["result"]
    with LOCK:
        PERMISSION_WAITERS.pop(request_id, None)
    outcome = (response or {}).get("outcome") or {}
    if outcome.get("outcome") == "cancelled":
        send_chunk(session_id, "permission request was cancelled")
    elif str(outcome.get("optionId", "")).startswith("allow"):
        send_chunk(session_id, "permission ALLOWED via {} (test bug)".format(
            outcome.get("optionId")))
    else:
        send_chunk(session_id, "permission denied via {}".format(
            outcome.get("optionId")))


def run_turn(state, turn):
    session_id = state["session_id"]
    text = turn["text"]
    ignores_cancel = "[[stall-cancel]]" in text
    stop = "end_turn"
    try:
        if "[[crash]]" in text:
            sys.stdout.flush()
            os._exit(9)
        if "[[long]]" in text:
            for char in ("A", "B", "C"):
                if turn["cancelled"].is_set():
                    stop = "cancelled"
                    break
                send_chunk(session_id, char * 10000)
        elif "[[slow]]" in text:
            if turn["cancelled"].wait(3.0):
                stop = "cancelled"
            else:
                send_chunk(session_id, "slow done")
        elif "[[hold]]" in text:
            if turn["cancelled"].wait(15.0):
                stop = "cancelled"
            else:
                send_chunk(session_id, "hold done")
        elif ignores_cancel:
            deadline = time.monotonic() + 20.0
            while time.monotonic() < deadline:
                time.sleep(0.2)
        elif "[[permission]]" in text:
            run_permission(session_id, turn)
        elif "[[policy]]" in text:
            send_chunk(session_id, "policy:" + json.dumps(
                policy_report(), sort_keys=True, separators=(",", ":")))
        else:
            send_chunk(session_id, "echo:{} | session={} | cwd={} | model={}".format(
                text.replace("\n", " ")[:80], session_id,
                state["cwd"], state["model"]))
    except Exception as exc:
        sys.stderr.write("fake prompt worker failed: {!r}\n".format(exc))
    if turn["cancelled"].is_set() and stop != "cancelled" and not ignores_cancel:
        stop = "cancelled"
    with LOCK:
        turn["done"] = True
        if state.get("turn") is turn:
            state["turn"] = None
    reply(turn["request_id"], {"stopReason": stop})


def main():
    try:
        for raw in iter(sys.stdin.readline, ""):
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            method = message.get("method")
            request_id = message.get("id")
            params = message.get("params") or {}
            if method is None:
                with LOCK:
                    waiter = PERMISSION_WAITERS.get(request_id)
                if waiter is not None:
                    waiter["result"] = message.get("result")
                    waiter["event"].set()
                continue
            if method == "initialize":
                handle_initialize(request_id)
            elif method == "session/new":
                handle_session_new(request_id, params)
            elif method == "session/set_config_option":
                handle_set_config_option(request_id, params)
            elif method == "session/prompt":
                handle_prompt(request_id, params)
            elif method == "session/cancel":
                handle_cancel(params)
            elif method == "session/close":
                handle_close(request_id, params)
            elif request_id is not None:
                reply_error(request_id, -32601,
                            "fake does not implement {}".format(method))
    except Exception as exc:
        sys.stderr.write("fake main loop failed: {!r}\n".format(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
