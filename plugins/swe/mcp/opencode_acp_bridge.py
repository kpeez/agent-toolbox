#!/usr/bin/env python3
"""MCP stdio bridge exposing direct OpenCode ACP sessions as MCP tools.

Runs one long-lived ``opencode acp`` child process (ACP v1, JSON-RPC over
stdio) on a single asyncio event loop and multiplexes independent sessions
across the MCP tools: spawn_agent, send_message, get_agent, list_agents,
wait_agents, interrupt_agent, close_agent.

Protocol references (shapes verified against the official docs):
  https://agentclientprotocol.com/          (ACP v1 schema + protocol pages)
  https://opencode.ai/docs/acp/             (OpenCode ACP support)

Behavioral rules:
- stdout carries only newline-delimited MCP JSON-RPC; diagnostics go to stderr.
- Tool access is denied by default. The child is launched with ``--pure`` and
  a deny-all permission policy. Only an explicit ``--permission-config`` file
  opts into tool access. OpenCode configuration is not an OS sandbox.
- ACP ``session/request_permission`` calls are always denied (a ``reject``
  option when offered, otherwise ``cancelled``) and recorded on the agent.
- ``--allowed-root`` is required; symlinks are resolved before a new agent's
  ``cwd`` is routed. It is routing, not a filesystem sandbox.
- An explicit ``model`` is applied through OpenCode's ACP ``model`` config
  option (``session/set_config_option``), including values nested in groups.
  If it cannot be selected the tool errors instead of silently falling back.
- One asyncio event loop owns all state, timers, and I/O. Waits are
  nonblocking, so status and cancel calls are never stuck behind a wait.
- No auto-restart: if the ACP child dies, every agent is marked failed and the
  operator restarts the bridge.

Usage: python3 opencode_acp_bridge.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import math
import os
import signal
import sys
import time
import traceback
from collections.abc import Callable, Mapping
from typing import Any

SERVER_NAME = "opencode-acp-bridge"
SERVER_VERSION = "0.2.0"

MCP_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
MCP_LATEST_PROTOCOL_VERSION = MCP_PROTOCOL_VERSIONS[-1]

ACP_PROTOCOL_VERSION = 1

STATE_RUNNING = "running"
STATE_IDLE = "idle"
STATE_FAILED = "failed"

MAX_BLOCKED_REASONS = 20
MAX_ACP_LINE_BYTES = 8 * 1024 * 1024
MAX_MCP_LINE_BYTES = 2 * 1024 * 1024
MAX_PENDING_CALLS = 64
MAX_PROMPT_CHARS = 1_000_000

Log = Callable[[str], None]

DEFAULT_OPENCODE_ARGS = ("acp", "--pure")


def child_env(base: Mapping[str, str], policy: dict[str, Any]) -> dict[str, str]:
    """Apply only the operator-selected permissions, without editing files."""
    env = dict(base)
    config = json.loads(env.get("OPENCODE_CONFIG_CONTENT") or "{}")
    if not isinstance(config, dict):
        raise ValueError("OPENCODE_CONFIG_CONTENT must be a JSON object")
    policy = {"*": "deny", **policy}
    policy.pop("task", None)
    policy["task"] = "deny"
    config.update(
        permission=policy,
        tools={"task": False},
        default_agent="build",
        share="disabled",
    )
    agents = config.setdefault("agent", {})
    if not isinstance(agents, dict):
        raise ValueError("OpenCode agent configuration must be an object")
    for entry in agents.values():
        if isinstance(entry, dict):
            entry["permission"] = policy
            entry["tools"] = {"task": False}
    build = agents.setdefault("build", {})
    if not isinstance(build, dict):
        raise ValueError("OpenCode build agent configuration must be an object")
    build["permission"] = policy
    build["tools"] = {"task": False}
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
    return env


class ToolError(Exception):
    """Tool-level failure surfaced as an MCP isError result."""


class BridgeTimeout(Exception):
    """A bounded wait expired."""


class ChildGone(Exception):
    """The ACP child process is not available."""


class RpcError(Exception):
    """The ACP peer answered a request with a JSON-RPC error."""

    def __init__(self, method: str, error: Any) -> None:
        self.method = method
        self.error = error or {}
        super().__init__(self.__str__())

    def __str__(self) -> str:
        err = self.error
        text = "{} error {}: {}".format(
            self.method, err.get("code"), err.get("message")
        )
        data = err.get("data")
        if data is not None:
            try:
                text += f" | data={json.dumps(data)[:500]}"
            except (TypeError, ValueError):
                pass
        return text


class StartupError(Exception):
    """The ACP child could not be launched or initialized."""


def text_of(block: Any) -> str:
    """Extract display text from an ACP content block, if any."""
    if isinstance(block, dict) and block.get("type") == "text":
        value = block.get("text")
        if isinstance(value, str) and value:
            return value
    return ""


def _consume_future_exception(fut: asyncio.Future) -> None:
    """Mark a future's exception as retrieved, avoiding GC warnings."""
    if not fut.cancelled():
        fut.exception()


class Turn:
    """One prompt turn. Cancellation is bound to this object, not to the agent.

    A watchdog or resolver only mutates agent state while the agent still
    points at this turn, so a late timer can never cancel a later turn.
    """

    __slots__ = (
        "cancel_waiter",
        "future",
        "pending_cancel",
        "resolved",
        "resolver",
        "timed_out",
        "watchdog",
    )

    def __init__(self) -> None:
        self.future: asyncio.Future | None = None
        self.resolved = False
        self.pending_cancel = False
        self.timed_out = False
        self.resolver: asyncio.Task | None = None
        self.watchdog: asyncio.Task | None = None
        self.cancel_waiter: asyncio.Task | None = None


class Agent:
    """State for one bridge agent backed by one ACP session."""

    __slots__ = (
        "blocked",
        "closing",
        "cwd",
        "dropped_chars",
        "error",
        "id",
        "model",
        "session_id",
        "state",
        "stop_reason",
        "text",
        "total_chars",
        "turn",
    )

    def __init__(
        self, agent_id: str, session_id: str, cwd: str, model: str | None
    ) -> None:
        self.id = agent_id
        self.session_id = session_id
        self.cwd = cwd
        self.model = model
        self.state = STATE_IDLE
        self.stop_reason: str | None = None
        self.error: str | None = None
        self.blocked: list[str] = []
        self.text = ""
        self.dropped_chars = 0
        self.total_chars = 0
        self.turn: Turn | None = None
        self.closing = False

    def append_text(self, text: str, limit: int) -> None:
        """Append output, retaining only the newest ``limit`` characters."""
        if not text:
            return
        self.total_chars += len(text)
        if len(text) >= limit:
            self.dropped_chars += len(self.text) + len(text) - limit
            self.text = text[-limit:]
            return
        self.text += text
        excess = len(self.text) - limit
        if excess > 0:
            self.text = self.text[excess:]
            self.dropped_chars += excess

    def summary(self) -> dict[str, Any]:
        return {
            "agent_id": self.id,
            "session_id": self.session_id,
            "state": self.state,
            "cwd": self.cwd,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "error": self.error,
        }


class AcpConnection:
    """The single long-lived ``opencode acp`` child and its JSON-RPC plumbing.

    All methods run on the owning event loop; there are no locks because no
    two coroutines can interleave between a state check and its update.
    """

    def __init__(
        self,
        command: list[str],
        args: list[str],
        startup_timeout: float,
        stderr_limit: int,
        env: Mapping[str, str],
        log: Log,
    ) -> None:
        self.command = list(command)
        self.args = list(args)
        self.startup_timeout = startup_timeout
        self.stderr_limit = max(1, int(stderr_limit))
        self.env = dict(env)
        self.log = log
        self.proc: asyncio.subprocess.Process | None = None
        self.ready = False
        self.dead = False
        self.exit_code: int | None = None
        self.startup_error: str | None = None
        self.close_supported = False
        self.auth_methods: list[Any] = []
        self.stderr_tail = bytearray()
        self._pending: dict[int, tuple[str, asyncio.Future]] = {}
        self._next_id = 0
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._bridge: Bridge = None  # type: ignore[assignment]

    # -- lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        """Spawn the child and run the ACP initialize handshake."""
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                limit=MAX_ACP_LINE_BYTES,
            )
        except (OSError, ValueError) as exc:
            raise StartupError(
                "cannot execute {!r}: {}".format(
                    " ".join(self.command + self.args), exc
                )
            )
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._pump_stderr())
        try:
            result = await self.call(
                "initialize",
                {
                    "protocolVersion": ACP_PROTOCOL_VERSION,
                    "clientCapabilities": {
                        "fs": {"readTextFile": False, "writeTextFile": False},
                        "terminal": False,
                    },
                    "clientInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
                timeout=self.startup_timeout,
            )
        except Exception:
            await self.shutdown()
            raise
        if not isinstance(result, dict):
            await self.shutdown()
            raise StartupError("initialize returned a non-object result")
        version = result.get("protocolVersion")
        if version != ACP_PROTOCOL_VERSION:
            await self.shutdown()
            raise StartupError(
                f"unsupported ACP protocol version {version!r} (need {ACP_PROTOCOL_VERSION!r})"
            )
        caps = result.get("agentCapabilities") or {}
        caps = caps if isinstance(caps, dict) else {}
        session_caps = caps.get("sessionCapabilities") or {}
        self.close_supported = (
            isinstance(session_caps, dict) and "close" in session_caps
        )
        methods = result.get("authMethods")
        self.auth_methods = methods if isinstance(methods, list) else []
        agent_info = result.get("agentInfo") or {}
        self.log(
            "ACP child initialized: {} v{} protocolVersion={}".format(
                agent_info.get("name", "?"), agent_info.get("version", "?"), version
            )
        )
        self.ready = True

    async def shutdown(self) -> None:
        """Terminate and reap the child, then drain its read tasks.

        The process is terminated and reaped before the read streams are
        abandoned, so a reader can never block shutdown forever on a stream
        lock.
        """
        proc = self.proc
        if proc is None:
            return
        if proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
        tasks = [t for t in (self._reader_task, self._stderr_task) if t is not None]
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=2)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    def stderr_snapshot(self, limit: int | None = None) -> str:
        if limit is None:
            limit = self.stderr_limit
        limit = max(0, int(limit))
        if limit <= 0:
            return ""
        return bytes(self.stderr_tail[-limit:]).decode("utf-8", "replace")

    async def _pump_stderr(self) -> None:
        proc = self.proc
        assert proc is not None and proc.stderr is not None
        try:
            while True:
                chunk = await proc.stderr.read(4096)
                if not chunk:
                    break
                self.stderr_tail.extend(chunk)
                overflow = len(self.stderr_tail) - self.stderr_limit
                if overflow > 0:
                    del self.stderr_tail[:overflow]
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    # -- wire helpers ------------------------------------------------------

    async def _write(self, message: dict[str, Any]) -> None:
        proc = self.proc
        if proc is None or self.dead or proc.stdin is None:
            raise ChildGone("ACP child is not running")
        data = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            proc.stdin.write(data)
            await asyncio.wait_for(proc.stdin.drain(), min(self.startup_timeout, 5))
        except (
            asyncio.TimeoutError,
            BrokenPipeError,
            ConnectionResetError,
            OSError,
            ValueError,
        ) as exc:
            raise ChildGone(f"ACP child stdin write failed: {exc}")

    async def send_request(
        self,
        method: str,
        params: Any | None = None,
    ) -> tuple[int, asyncio.Future]:
        if self.dead or self.proc is None:
            raise ChildGone("ACP child is not running")
        self._next_id += 1
        request_id = self._next_id
        fut = asyncio.get_running_loop().create_future()
        fut.add_done_callback(_consume_future_exception)
        self._pending[request_id] = (method, fut)
        fut.add_done_callback(
            lambda completed: (
                self._pending.pop(request_id, None) if completed.cancelled() else None
            )
        )
        request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        try:
            await self._write(request)
        except ChildGone:
            self._pending.pop(request_id, None)
            raise
        return request_id, fut

    async def call(self, method: str, params: Any | None, timeout: float) -> Any:
        request_id, fut = await self.send_request(method, params)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            fut.cancel()
            raise BridgeTimeout(f"{method} timed out after {timeout}s")

    async def notify(self, method: str, params: Any) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    # -- inbound traffic ---------------------------------------------------

    async def _read_loop(self) -> None:
        proc = self.proc
        assert proc is not None and proc.stdout is not None
        try:
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    self.log(f"discarding non-JSON line from ACP child: {line[:200]!r}")
                    continue
                if isinstance(message, dict):
                    await self._dispatch_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.log(f"ACP reader loop stopped: {exc!r}")
        finally:
            await self._on_exit()

    async def _dispatch_message(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method is not None:
            request_id = message.get("id")
            params = message.get("params") or {}
            if request_id is None:
                self._handle_notification(method, params)
            else:
                await self._handle_agent_request(method, request_id, params)
            return
        request_id = message.get("id")
        entry = self._pending.pop(request_id, None)
        if entry is None:
            self.log(f"ignoring response for unknown request id {request_id!r}")
            return
        method, fut = entry
        if fut.done():
            return
        if message.get("error") is not None:
            fut.set_exception(RpcError(method, message.get("error")))
        else:
            fut.set_result(message.get("result"))

    def _handle_notification(self, method: str, params: Any) -> None:
        if method == "session/update":
            self._bridge.on_session_update(params)
        else:
            self.log(f"ignoring ACP notification {method}")

    async def _handle_agent_request(
        self, method: str, request_id: Any, params: Any
    ) -> None:
        try:
            if method == "session/request_permission":
                result: Any = {"outcome": self._deny_permission(params)}
            elif method == "elicitation/create":
                result = {"action": "cancel"}
            else:
                # fs/* and terminal/* are never advertised by this client; an
                # agent calling them anyway gets a protocol error.
                await self._write(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"bridge does not support agent method {method}",
                        },
                    }
                )
                return
            await self._write({"jsonrpc": "2.0", "id": request_id, "result": result})
        except ChildGone:
            pass
        except Exception as exc:
            self.log(f"failed handling ACP request {method}:\n{traceback.format_exc()}")
            try:
                await self._write(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"bridge internal error handling {method}: {exc}",
                        },
                    }
                )
            except ChildGone:
                pass

    def _deny_permission(self, params: Any) -> dict[str, Any]:
        """Answer a permission request with a denial and record the reason."""
        session_id = params.get("sessionId")
        tool_call = params.get("toolCall") or {}
        options = params.get("options") or []
        reject = None
        for kind in ("reject_once", "reject_always"):
            for option in options:
                if isinstance(option, dict) and option.get("kind") == kind:
                    reject = option
                    break
            if reject is not None:
                break
        if reject is None:
            for option in options:
                if isinstance(option, dict) and str(option.get("kind", "")).startswith(
                    "reject"
                ):
                    reject = option
                    break
        agent = self._bridge.agent_by_session(session_id)
        cancelling = (
            agent is not None and agent.turn is not None and agent.turn.pending_cancel
        )
        if cancelling or reject is None:
            outcome: dict[str, Any] = {"outcome": "cancelled"}
            choice = "cancelled"
        else:
            outcome = {"outcome": "selected", "optionId": reject.get("optionId")}
            choice = str(reject.get("kind"))
        if agent is not None:
            reason = "permission {}: toolCallId={} title={!r}".format(
                choice, tool_call.get("toolCallId"), tool_call.get("title")
            )
            if cancelling:
                reason += " (turn was being cancelled)"
            agent.blocked.append(reason)
            del agent.blocked[:-MAX_BLOCKED_REASONS]
        self.log(f"denied ACP permission request for session {session_id!r}: {choice}")
        return outcome

    async def _on_exit(self) -> None:
        if self.dead:
            return
        self.dead = True
        entries = list(self._pending.values())
        self._pending.clear()
        for method, fut in entries:
            if not fut.done():
                fut.set_exception(
                    ChildGone(f"ACP child exited while awaiting {method}")
                )
        code: int | None = None
        if self.proc is not None:
            try:
                code = await asyncio.wait_for(self.proc.wait(), timeout=2)
            except (asyncio.TimeoutError, ProcessLookupError):
                code = self.proc.returncode
        self.exit_code = code
        tail = self.stderr_snapshot()
        self._bridge.on_child_exit(code, tail)


class Bridge:
    """Owns agents, the ACP child, and the MCP tool implementations."""

    def __init__(self, cfg: Config, log: Log) -> None:
        self.cfg = cfg
        self.log = log
        self._stopping = False
        self._agents: dict[str, Agent] = {}
        self._by_session: dict[str, Agent] = {}
        self._next_agent_num = 0
        self._reserved = 0
        self._shutdown_done = False
        self._startup_lock: asyncio.Lock | None = None
        self.acp = AcpConnection(
            [cfg.opencode],
            cfg.opencode_args,
            cfg.startup_timeout,
            cfg.stderr_limit,
            child_env(os.environ, cfg.permission_policy),
            log,
        )
        self.acp._bridge = self

    # -- lookups -----------------------------------------------------------

    def request_stop(self) -> None:
        self._stopping = True

    def agent_by_session(self, session_id: str | None) -> Agent | None:
        if session_id is None:
            return None
        return self._by_session.get(session_id)

    def _require_agent(self, agent_id: str) -> Agent:
        agent = self._agents.get(agent_id)
        if agent is None:
            raise ToolError(
                f"unknown agent_id {agent_id!r}; use list_agents for live ids"
            )
        return agent

    # -- ACP child management ---------------------------------------------

    async def _ensure_child(self) -> None:
        acp = self.acp
        if acp.ready and not acp.dead:
            return
        if acp.startup_error:
            raise ToolError(f"OpenCode ACP startup failed: {acp.startup_error}")
        if acp.dead:
            raise ToolError(
                f"OpenCode ACP process exited (code {acp.exit_code!r}); restart the bridge to "
                "continue"
            )
        if self._startup_lock is None:
            self._startup_lock = asyncio.Lock()
        async with self._startup_lock:
            if acp.ready and not acp.dead:
                return
            try:
                await acp.start()
            except BridgeTimeout as exc:
                acp.startup_error = str(exc)
                raise ToolError(f"OpenCode ACP startup failed: {exc}")
            except (StartupError, RpcError, ChildGone) as exc:
                detail = str(exc)
                tail = acp.stderr_snapshot()
                if tail:
                    detail += f" | stderr tail: {tail}"
                acp.startup_error = detail
                raise ToolError(f"OpenCode ACP startup failed: {detail}")

    def on_child_exit(self, code: int | None, tail: str) -> None:
        self.acp.exit_code = code
        message = f"OpenCode ACP process exited (code {code!r})"
        if tail:
            message += f"; stderr tail: {tail}"
        # A dead child makes every session unusable, idle or running.
        for agent in self._agents.values():
            if agent.turn is not None and not agent.turn.resolved:
                self._finish_turn(agent.turn)
            if agent.state != STATE_FAILED:
                agent.state = STATE_FAILED
                agent.error = message
        self.log(message)

    def on_session_update(self, params: Any) -> None:
        session_id = params.get("sessionId")
        update = params.get("update") or {}
        kind = update.get("sessionUpdate")
        agent = self.agent_by_session(session_id)
        if agent is None or agent.state == STATE_FAILED:
            return
        if kind == "agent_message_chunk":
            text = text_of(update.get("content"))
            if text:
                agent.append_text(text, self.cfg.max_output_chars)
        elif kind in ("tool_call", "tool_call_update"):
            if kind == "tool_call":
                title = update.get("title")
                if title:
                    agent.append_text(
                        "[tool {}] {}\n".format(update.get("kind") or "other", title),
                        self.cfg.max_output_chars,
                    )
            for block in update.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "content":
                    text = text_of(block.get("content"))
                    if text:
                        agent.append_text(text, self.cfg.max_output_chars)

    # -- prompt lifecycle --------------------------------------------------

    def _reserve_turn(self, agent: Agent) -> Turn:
        """Atomically move an idle agent to running and return its turn."""
        if agent.closing:
            raise ToolError(f"agent {agent.id} is closing")
        if agent.state != STATE_IDLE:
            raise ToolError(
                f"agent {agent.id} is {agent.state}; only idle agents accept prompts"
            )
        turn = Turn()
        agent.turn = turn
        agent.state = STATE_RUNNING
        agent.stop_reason = None
        agent.error = None
        return turn

    async def _begin_turn(self, agent: Agent, prompt: str) -> Turn:
        turn = self._reserve_turn(agent)
        try:
            _, fut = await self.acp.send_request(
                "session/prompt",
                {
                    "sessionId": agent.session_id,
                    "prompt": [{"type": "text", "text": prompt}],
                },
            )
        except ChildGone as exc:
            self._finish_turn(turn)
            if agent.turn is turn:
                agent.state = STATE_FAILED
                agent.error = "ACP child exited before the prompt could be sent"
            raise ToolError(f"OpenCode ACP child is gone: {exc}")
        turn.future = fut
        turn.resolver = asyncio.create_task(self._resolve_turn(agent, turn))
        if self.cfg.prompt_timeout > 0:
            turn.watchdog = asyncio.create_task(self._watchdog(agent, turn))
        return turn

    @staticmethod
    def _finish_turn(turn: Turn) -> None:
        """Mark a turn resolved and stop its now-useless watchdog timer."""
        turn.resolved = True
        if turn.watchdog is not None and not turn.watchdog.done():
            turn.watchdog.cancel()
        if turn.cancel_waiter is not None and not turn.cancel_waiter.done():
            turn.cancel_waiter.cancel()

    async def _resolve_turn(self, agent: Agent, turn: Turn) -> None:
        try:
            result = await turn.future
        except asyncio.CancelledError:
            raise
        except ChildGone:
            self._finish_turn(turn)
            return
        except RpcError as exc:
            self._finish_turn(turn)
            if agent.turn is turn:
                if turn.pending_cancel or turn.timed_out:
                    agent.state = STATE_IDLE
                    agent.stop_reason = "cancelled"
                    agent.error = f"session/prompt errored during cancellation: {exc}"
                else:
                    agent.state = STATE_FAILED
                    agent.error = str(exc)
            return
        self._finish_turn(turn)
        if agent.turn is turn:
            if not isinstance(result, dict) or not isinstance(
                result.get("stopReason"), str
            ):
                agent.state = STATE_FAILED
                agent.error = "session/prompt returned no valid stopReason"
                return
            agent.stop_reason = result["stopReason"]
            agent.state = STATE_IDLE
            agent.error = None
            if turn.timed_out:
                agent.error = (
                    f"prompt exceeded --prompt-timeout ({self.cfg.prompt_timeout}s); cancel resolved the "
                    f"turn with stopReason={agent.stop_reason!r}"
                )

    async def _watchdog(self, agent: Agent, turn: Turn) -> None:
        try:
            await asyncio.sleep(self.cfg.prompt_timeout)
        except asyncio.CancelledError:
            return
        if agent.turn is not turn or turn.resolved:
            return
        turn.timed_out = True
        turn.pending_cancel = True
        try:
            await self.acp.notify("session/cancel", {"sessionId": agent.session_id})
        except ChildGone:
            return
        if turn.future is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(turn.future), self.cfg.cancel_timeout)
        except asyncio.TimeoutError:
            if agent.turn is turn and not turn.resolved:
                agent.state = STATE_FAILED
                agent.error = (
                    f"prompt exceeded --prompt-timeout ({self.cfg.prompt_timeout}s) and session/cancel did "
                    f"not resolve the turn within --cancel-timeout ({self.cfg.cancel_timeout}s); the ACP "
                    "turn is still open"
                )
        except (ChildGone, RpcError, asyncio.CancelledError):
            pass

    async def _send_cancel(self, agent: Agent) -> bool:
        try:
            await self.acp.notify("session/cancel", {"sessionId": agent.session_id})
            return True
        except ChildGone as exc:
            self.log(f"could not send session/cancel: {exc}")
            return False

    async def _observe_cancel(self, agent: Agent, turn: Turn) -> None:
        deadline = time.monotonic() + self.cfg.cancel_timeout
        while agent.turn is turn and not turn.resolved:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                agent.state = STATE_FAILED
                agent.error = (
                    "session/cancel stalled; the unresolved prompt still holds its slot"
                )
                return
            await asyncio.sleep(min(0.05, remaining))

    # -- tool implementations ---------------------------------------------

    def validate_cwd(self, cwd: str) -> str:
        if not os.path.isabs(cwd):
            raise ToolError(f"cwd must be an absolute path, got {cwd!r}")
        real = os.path.realpath(cwd)
        roots = self.cfg.allowed_roots
        if not any(
            real == root or real.startswith(root.rstrip(os.sep) + os.sep)
            for root in roots
        ):
            raise ToolError(
                "cwd {!r} (resolved {!r}) is not under an --allowed-root ({}); "
                "this routes agents, it is not a security sandbox".format(
                    cwd, real, "; ".join(roots)
                )
            )
        if not os.path.isdir(real):
            raise ToolError(f"cwd {cwd!r} is not an existing directory")
        return real

    @staticmethod
    def _find_model_option(config_options: Any) -> dict[str, Any] | None:
        for option in config_options or []:
            if isinstance(option, dict) and option.get("category") == "model":
                return option
        for option in config_options or []:
            if isinstance(option, dict) and option.get("id") == "model":
                return option
        return None

    @classmethod
    def _collect_values(cls, options: Any) -> list[str]:
        """Flatten a select option's values, recursing into groups."""
        values: list[str] = []
        for entry in options or []:
            if not isinstance(entry, dict):
                continue
            value = entry.get("value")
            if isinstance(value, str):
                values.append(value)
            values.extend(cls._collect_values(entry.get("options")))
        return values

    async def _apply_model(
        self, session_id: str, model: str, option: dict[str, Any]
    ) -> None:
        """Select an explicit model and verify OpenCode actually applied it."""
        new = await self.acp.call(
            "session/set_config_option",
            {"sessionId": session_id, "configId": option.get("id"), "value": model},
            timeout=self.cfg.startup_timeout,
        )
        applied = None
        for updated in (new or {}).get("configOptions") or []:
            if isinstance(updated, dict) and updated.get("id") == option.get("id"):
                applied = updated
                break
        if applied is None or applied.get("currentValue") != model:
            current = applied.get("currentValue") if applied else None
            raise ToolError(
                f"OpenCode did not apply model {model!r} (currentValue={current!r}); refusing "
                "to fall back to a default"
            )

    async def _new_session(self, cwd: str) -> tuple[str, dict[str, Any]]:
        try:
            result = await self.acp.call(
                "session/new",
                {"cwd": cwd, "mcpServers": []},
                timeout=self.cfg.startup_timeout,
            )
        except BridgeTimeout as exc:
            raise ToolError(str(exc))
        except RpcError as exc:
            hint = ""
            if "auth" in str(exc).lower() and self.acp.auth_methods:
                hint = (
                    " (OpenCode advertises authMethods {}; authenticate "
                    "OpenCode yourself, the bridge never does)".format(
                        [
                            m.get("id")
                            for m in self.acp.auth_methods
                            if isinstance(m, dict)
                        ]
                    )
                )
            raise ToolError(f"session/new failed: {exc}{hint}")
        except ChildGone as exc:
            raise ToolError(f"OpenCode ACP child died during session/new: {exc}")
        if not isinstance(result, dict):
            raise ToolError("session/new returned a non-object result")
        session_id = result.get("sessionId")
        if not session_id:
            raise ToolError(
                f"session/new returned no sessionId: {json.dumps(result)[:300]}"
            )
        return session_id, result

    async def spawn_agent(
        self, prompt: str, cwd: str, model: str | None
    ) -> dict[str, Any]:
        if self._stopping:
            raise ToolError("bridge is shutting down")
        self._check_prompt(prompt)
        cwd = self.validate_cwd(cwd)
        await self._ensure_child()
        active = len(self._agents) + self._reserved
        if active >= self.cfg.max_sessions:
            raise ToolError(
                f"session limit reached ({active} active, --max-sessions {self.cfg.max_sessions}); close an "
                "agent first"
            )
        self._reserved += 1
        agent: Agent | None = None
        session_id: str | None = None
        try:
            session_id, result = await self._new_session(cwd)
            config_options = result.get("configOptions") or []
            option = self._find_model_option(config_options)
            if model is not None:
                if option is None:
                    raise ToolError(
                        f"model {model!r} requested but OpenCode advertises no model "
                        "config option; refusing to fall back to the default "
                        "model"
                    )
                offered = self._collect_values(option.get("options"))
                if model not in offered:
                    raise ToolError(
                        f"model {model!r} is not offered by OpenCode; available values: "
                        f"{offered}"
                    )
                await self._apply_model(session_id, model, option)
            elif option is not None:
                model = option.get("currentValue")
            self._next_agent_num += 1
            agent = Agent(f"agent-{self._next_agent_num}", session_id, cwd, model)
            self._agents[agent.id] = agent
            self._by_session[session_id] = agent
        except Exception:
            if agent is not None:
                self._agents.pop(agent.id, None)
                self._by_session.pop(agent.session_id, None)
                session_id = agent.session_id
            if session_id is not None:
                await self._close_acp_session(session_id)
            raise
        finally:
            self._reserved -= 1
        try:
            await self._begin_turn(agent, prompt)
        except Exception:
            self._agents.pop(agent.id, None)
            self._by_session.pop(agent.session_id, None)
            await self._close_acp_session(agent.session_id)
            raise
        return {
            "agent_id": agent.id,
            "session_id": agent.session_id,
            "state": agent.state,
            "cwd": agent.cwd,
            "model": agent.model,
        }

    async def send_message(self, agent_id: str, prompt: str) -> dict[str, Any]:
        if self._stopping:
            raise ToolError("bridge is shutting down")
        self._check_prompt(prompt)
        agent = self._require_agent(agent_id)
        if agent.closing:
            raise ToolError(f"agent {agent_id} is closing")
        if agent.state == STATE_RUNNING:
            raise ToolError(
                f"agent {agent_id} is running; wait for it to resolve or interrupt_agent "
                "first (messages are never queued)"
            )
        if agent.state != STATE_IDLE:
            raise ToolError(
                f"agent {agent_id} is {agent.state}; only idle agents accept prompts"
            )
        try:
            await self._ensure_child()
        except ToolError:
            # A failed send must not leave the agent looking idle.
            if agent.state == STATE_IDLE:
                agent.state = STATE_FAILED
                agent.error = "OpenCode ACP child is not available"
            raise
        await self._begin_turn(agent, prompt)
        return {"agent_id": agent_id, "state": agent.state}

    def _check_prompt(self, prompt: str) -> None:
        if len(prompt) > MAX_PROMPT_CHARS:
            raise ToolError(
                f"prompt is {len(prompt)} chars; the bridge limit is {MAX_PROMPT_CHARS}"
            )

    def get_agent(self, agent_id: str, cursor: int) -> dict[str, Any]:
        agent = self._require_agent(agent_id)
        full = agent.text
        start = max(cursor, agent.dropped_chars)
        text = full[start - agent.dropped_chars :]
        return {
            "agent_id": agent.id,
            "session_id": agent.session_id,
            "state": agent.state,
            "cwd": agent.cwd,
            "model": agent.model,
            "stop_reason": agent.stop_reason,
            "error": agent.error,
            "blocked_reasons": list(agent.blocked),
            "output": {
                "text": text,
                "next_cursor": agent.dropped_chars + len(full),
                "total_chars": agent.total_chars,
                "dropped_chars": agent.dropped_chars,
                "truncated": agent.dropped_chars > 0,
                "has_more": agent.state == STATE_RUNNING,
            },
        }

    def list_agents(self) -> dict[str, Any]:
        return {
            "limit": self.cfg.max_sessions,
            "count": len(self._agents),
            "agents": [
                agent.summary()
                for agent in sorted(self._agents.values(), key=lambda a: a.id)
            ],
        }

    async def wait_agents(self, agent_ids: list[str], timeout: float) -> dict[str, Any]:
        agents = [self._require_agent(agent_id) for agent_id in agent_ids]
        deadline = time.monotonic() + min(timeout, 60.0)
        timed_out = False
        while any(agent.state == STATE_RUNNING for agent in agents):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self._stopping:
                timed_out = True
                break
            # Yielding keeps every other MCP request responsive.
            await asyncio.sleep(min(0.2, remaining))
        return {
            "timed_out": timed_out,
            "agents": {
                agent.id: {
                    "state": agent.state,
                    "stop_reason": agent.stop_reason,
                    "error": agent.error,
                }
                for agent in agents
            },
        }

    async def interrupt_agent(self, agent_id: str) -> dict[str, Any]:
        if self._stopping:
            raise ToolError("bridge is shutting down")
        agent = self._require_agent(agent_id)
        turn = agent.turn
        if agent.state != STATE_RUNNING or turn is None or turn.resolved:
            return {
                "agent_id": agent_id,
                "state": agent.state,
                "interrupt_requested": False,
                "stop_reason": agent.stop_reason,
                "error": agent.error,
            }
        turn.pending_cancel = True
        sent = await self._send_cancel(agent)
        if sent and turn.cancel_waiter is None:
            turn.cancel_waiter = asyncio.create_task(self._observe_cancel(agent, turn))
        if not sent and self.acp.dead:
            raise ToolError("OpenCode ACP process exited; the agent is marked failed")
        return {
            "agent_id": agent_id,
            "state": agent.state,
            "interrupt_requested": sent,
            "stop_reason": None,
            "error": None,
        }

    async def _close_acp_session(self, session_id: str) -> bool:
        """Best-effort ACP session/close; only when OpenCode advertises it."""
        if not (self.acp.ready and self.acp.close_supported and not self.acp.dead):
            return False
        try:
            await self.acp.call("session/close", {"sessionId": session_id}, timeout=2)
            return True
        except (BridgeTimeout, RpcError, ChildGone) as exc:
            self.log(f"session/close failed for {session_id!r}: {exc}")
            return False

    async def close_agent(self, agent_id: str) -> dict[str, Any]:
        if self._stopping:
            raise ToolError("bridge is shutting down")
        agent = self._require_agent(agent_id)
        agent.closing = True
        turn = agent.turn
        cancel_stalled = False
        if agent.state == STATE_RUNNING and turn is not None and not turn.resolved:
            turn.pending_cancel = True
            await self._send_cancel(agent)
            if turn.future is not None:
                try:
                    await asyncio.wait_for(
                        asyncio.shield(turn.future), self.cfg.cancel_timeout
                    )
                except asyncio.TimeoutError:
                    pass
                except (ChildGone, RpcError, asyncio.CancelledError):
                    pass
            if agent.state == STATE_RUNNING and not turn.resolved:
                cancel_stalled = True
        acp_closed = await self._close_acp_session(agent.session_id)
        turn_open = turn is not None and not turn.resolved
        if turn_open and not acp_closed:
            # Keep the recoverable state and its slot: the ACP turn is still
            # open, so removing the record would orphan a running session.
            agent.closing = False
            return {
                "agent_id": agent_id,
                "closed": False,
                "cancel_stalled": cancel_stalled,
                "acp_session_closed": False,
                "error": (
                    "session still has an unresolved prompt; it was not "
                    "closed and still holds a slot"
                ),
            }
        self._agents.pop(agent_id, None)
        self._by_session.pop(agent.session_id, None)
        if turn is not None:
            self._finish_turn(turn)
            if turn.resolver is not None and not turn.resolver.done():
                turn.resolver.cancel()
                await asyncio.gather(turn.resolver, return_exceptions=True)
        return {
            "agent_id": agent_id,
            "closed": True,
            "cancel_stalled": cancel_stalled,
            "acp_session_closed": acp_closed,
        }

    # -- shutdown ----------------------------------------------------------

    async def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._stopping = True
        agents = list(self._agents.values())
        cancelling = [
            self._send_cancel(agent)
            for agent in agents
            if agent.turn is not None and not agent.turn.resolved
        ]
        if cancelling:
            try:
                await asyncio.wait_for(asyncio.gather(*cancelling), timeout=2)
            except asyncio.TimeoutError:
                pass
        deadline = time.monotonic() + 4
        for agent in agents:
            if time.monotonic() > deadline:
                break
            if agent.turn is None or agent.turn.resolved:
                await self._close_acp_session(agent.session_id)
        await self.acp.shutdown()
        leftovers = [
            task
            for agent in agents
            if agent.turn is not None
            for task in (
                agent.turn.watchdog,
                agent.turn.resolver,
                agent.turn.cancel_waiter,
            )
            if task is not None and not task.done()
        ]
        for task in leftovers:
            task.cancel()
        if leftovers:
            await asyncio.gather(*leftovers, return_exceptions=True)


# ---------------------------------------------------------------------------
# MCP layer
# ---------------------------------------------------------------------------


def tool_definitions() -> list[dict[str, Any]]:
    schemas = {
        "spawn_agent": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "minLength": 1,
                    "description": "First prompt to run in the new agent.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Absolute working directory for the agent; "
                    "must resolve under an --allowed-root "
                    "(routing only, not a sandbox).",
                },
                "model": {
                    "type": "string",
                    "description": "Optional explicit model, applied through "
                    "OpenCode's ACP model config option. Fails "
                    "if OpenCode does not offer it; never "
                    "falls back.",
                },
            },
            "required": ["prompt", "cwd"],
            "additionalProperties": False,
        },
        "send_message": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "prompt": {"type": "string", "minLength": 1},
            },
            "required": ["agent_id", "prompt"],
            "additionalProperties": False,
        },
        "get_agent": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "cursor": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Opaque offset from a previous "
                    "next_cursor; 0 reads from the oldest "
                    "retained output.",
                },
            },
            "required": ["agent_id"],
            "additionalProperties": False,
        },
        "list_agents": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "wait_agents": {
            "type": "object",
            "properties": {
                "agent_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "timeout": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": 60,
                    "description": "Seconds to wait; max 60. Default 30.",
                },
            },
            "required": ["agent_ids"],
            "additionalProperties": False,
        },
        "interrupt_agent": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
            "additionalProperties": False,
        },
        "close_agent": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
            "additionalProperties": False,
        },
    }
    descriptions = {
        "spawn_agent": (
            "Start a new OpenCode ACP agent session and immediately run `prompt` "
            "in it. Returns {agent_id, session_id, state} promptly; poll get_agent "
            "or use wait_agents for output and completion."
        ),
        "send_message": (
            "Send a follow-up prompt to an idle agent over the same retained ACP "
            "session. Rejected while the agent is running or failed; never queued."
        ),
        "get_agent": (
            "Snapshot an agent: state, stop reason, errors, blocked-permission "
            "reasons, and bounded transcript text starting at `cursor`. Transcript "
            "is tail-truncated to --max-output-chars; use output.next_cursor to "
            "continue."
        ),
        "list_agents": (
            "List live agents (state, cwd, model, stop reason) and the configured "
            "session limit."
        ),
        "wait_agents": (
            "Wait until every listed agent is not running (idle/failed) or until "
            "timeout (max 60s). Other tool calls stay responsive while this waits."
        ),
        "interrupt_agent": (
            "Send ACP session/cancel to a running agent and answer any pending "
            "permission request as cancelled. Returns immediately; the agent stays "
            "'running' until the turn actually resolves."
        ),
        "close_agent": (
            "Cancel the agent if running (waiting up to --cancel-timeout). If the "
            "turn resolves or OpenCode's advertised session/close succeeds, release "
            "its slot; otherwise keep it and report the stall instead of orphaning "
            "the session."
        ),
    }
    return [
        {
            "name": name,
            "description": descriptions[name],
            "inputSchema": schemas[name],
        }
        for name in (
            "spawn_agent",
            "send_message",
            "get_agent",
            "list_agents",
            "wait_agents",
            "interrupt_agent",
            "close_agent",
        )
    ]


def need_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{key} must be a non-empty string")
    return value


def opt_str(args: dict[str, Any], key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{key} must be a non-empty string when present")
    return value


def need_cursor(args: dict[str, Any]) -> int:
    value = args.get("cursor", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ToolError("cursor must be a non-negative integer")
    return value


def need_timeout(args: dict[str, Any]) -> float:
    value = args.get("timeout", 30.0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError("timeout must be a number of seconds (max 60)")
    if not (0 < value <= 60):
        raise ToolError(f"timeout must be > 0 and <= 60 seconds, got {value!r}")
    return float(value)


def need_agent_ids(args: dict[str, Any]) -> list[str]:
    value = args.get("agent_ids")
    if not isinstance(value, list) or not value:
        raise ToolError("agent_ids must be a non-empty array of agent ids")
    for item in value:
        if not isinstance(item, str) or not item:
            raise ToolError("agent_ids entries must be non-empty strings")
    return value


TOOL_HANDLERS = frozenset(
    {
        "spawn_agent",
        "send_message",
        "get_agent",
        "list_agents",
        "wait_agents",
        "interrupt_agent",
        "close_agent",
    }
)


class McpDispatcher:
    def __init__(self, bridge: Bridge, log: Log) -> None:
        self.bridge = bridge
        self.log = log

    def initialize(self, params: Any) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        if isinstance(requested, str) and requested in MCP_PROTOCOL_VERSIONS:
            version = requested
        else:
            version = MCP_LATEST_PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }

    async def call_tool(self, params: Any) -> dict[str, Any]:
        name = params.get("name")
        if name not in TOOL_HANDLERS:
            raise ToolError(f"unknown tool {name!r}")
        args = params.get("arguments")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ToolError("tool arguments must be an object")
        bridge = self.bridge
        if name == "spawn_agent":
            result = await bridge.spawn_agent(
                need_str(args, "prompt"), need_str(args, "cwd"), opt_str(args, "model")
            )
        elif name == "send_message":
            result = await bridge.send_message(
                need_str(args, "agent_id"), need_str(args, "prompt")
            )
        elif name == "get_agent":
            result = bridge.get_agent(need_str(args, "agent_id"), need_cursor(args))
        elif name == "list_agents":
            result = bridge.list_agents()
        elif name == "wait_agents":
            result = await bridge.wait_agents(need_agent_ids(args), need_timeout(args))
        elif name == "interrupt_agent":
            result = await bridge.interrupt_agent(need_str(args, "agent_id"))
        else:  # close_agent
            result = await bridge.close_agent(need_str(args, "agent_id"))
        return {
            "content": [{"type": "text", "text": json.dumps(result)}],
            "structuredContent": result,
        }

    async def handle(
        self, message: dict[str, Any], write: Callable[[dict[str, Any]], None]
    ) -> None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        try:
            if method == "initialize":
                result = self.initialize(params)
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": tool_definitions()}
            elif method == "tools/call":
                result = await self.call_tool(params)
            else:
                raise KeyError(method)
        except KeyError:
            write(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"method not found: {method!r}",
                    },
                }
            )
        except ToolError as exc:
            write(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                }
            )
        except ChildGone as exc:
            write(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"OpenCode ACP child is gone: {exc}",
                            }
                        ],
                        "isError": True,
                    },
                }
            )
        except Exception as exc:
            self.log(f"internal error handling {method}:\n{traceback.format_exc()}")
            write(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32603, "message": f"internal error: {exc}"},
                }
            )
        else:
            write({"jsonrpc": "2.0", "id": request_id, "result": result})


async def _next_line(
    incoming: asyncio.StreamReader, stop: asyncio.Event
) -> bytes | None:
    """Await the next stdin line or a stop signal, whichever comes first."""
    get_task = asyncio.create_task(incoming.readline())
    stop_task = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait(
            {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        for task in (get_task, stop_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(get_task, stop_task, return_exceptions=True)
    if stop.is_set():
        return None
    if get_task in done:
        return get_task.result() or None
    return None


async def serve(bridge: Bridge, log: Log) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    incoming = asyncio.StreamReader(limit=MAX_MCP_LINE_BYTES)
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(incoming), sys.stdin.buffer
    )
    try:
        loop.add_signal_handler(signal.SIGTERM, stop.set)
    except (NotImplementedError, RuntimeError):
        pass

    dispatcher = McpDispatcher(bridge, log)

    def write(message: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    tasks: set[asyncio.Task] = set()
    try:
        while True:
            try:
                raw = await _next_line(incoming, stop)
            except ValueError:
                write(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32600,
                            "message": "MCP input line exceeds 2 MiB",
                        },
                    }
                )
                break
            if raw is None:
                break
            line = raw.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                write(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "parse error: line is not valid JSON",
                        },
                    }
                )
                continue
            if not isinstance(message, dict) or not isinstance(
                message.get("method"), str
            ):
                write(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id") if isinstance(message, dict) else None,
                        "error": {"code": -32600, "message": "invalid request"},
                    }
                )
                continue
            if message.get("id") is None:
                # Notifications need no response; only lifecycle ones exist.
                continue
            params = message.get("params", {})
            if not isinstance(params, dict):
                write(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {
                            "code": -32602,
                            "message": "params must be an object",
                        },
                    }
                )
                continue
            control = message["method"] in ("ping", "tools/list") or (
                message["method"] == "tools/call"
                and params.get("name")
                in ("get_agent", "list_agents", "interrupt_agent")
            )
            if len(tasks) >= MAX_PENDING_CALLS and not control:
                write(
                    {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {
                            "code": -32000,
                            "message": "too many pending requests; retry after completion",
                        },
                    }
                )
                continue
            task = asyncio.create_task(dispatcher.handle(message, write))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
    finally:
        transport.close()
        bridge.request_stop()
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=10)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        await bridge.shutdown()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def permission_config(value: str) -> dict[str, Any]:
    try:
        with open(value, encoding="utf-8") as source:
            policy = json.load(source)
        if not isinstance(policy, dict):
            raise ValueError("expected a JSON permission object")
        for tool, rule in policy.items():
            actions = rule.values() if isinstance(rule, dict) else [rule]
            if not all(
                isinstance(action, str) and action in ("allow", "ask", "deny")
                for action in actions
            ):
                raise ValueError(f"invalid permission rule for {tool}")
            if tool != "task" and fnmatch.fnmatchcase("task", tool) and any(
                action != "deny" for action in actions
            ):
                raise ValueError(
                    f"permission rule {tool!r} can match task; nested delegation "
                    "is always disabled"
                )
        if policy.get("*", "deny") == "allow":
            raise ValueError(
                "wildcard allow is not supported; grant specific tool permissions"
            )
        return {"*": "deny", **policy}
    except (OSError, ValueError) as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def allowed_root(value: str) -> str:
    expanded = os.path.expanduser(value)
    if not os.path.isabs(expanded):
        raise argparse.ArgumentTypeError(
            f"--allowed-root must be an absolute path: {value}"
        )
    expanded = os.path.realpath(expanded)
    if not os.path.isdir(expanded):
        raise argparse.ArgumentTypeError(
            f"--allowed-root must be an existing directory: {value}"
        )
    return expanded


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer")
    if number < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return number


def non_negative(value: str, minimum: float) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number")
    if not math.isfinite(number) or number < minimum:
        raise argparse.ArgumentTypeError(f"must be >= {minimum}")
    return number


class Config:
    def __init__(self, ns: argparse.Namespace) -> None:
        self.opencode: str = ns.opencode
        # Replacement args win; the default is used only when none were given.
        self.opencode_args: list[str] = (
            list(ns.opencode_args) if ns.opencode_args else list(DEFAULT_OPENCODE_ARGS)
        )
        self.allowed_roots: list[str] = ns.allowed_roots
        self.max_sessions: int = ns.max_sessions
        self.max_output_chars: int = ns.max_output_chars
        self.startup_timeout: float = ns.startup_timeout
        self.prompt_timeout: float = ns.prompt_timeout
        self.cancel_timeout: float = ns.cancel_timeout
        self.stderr_limit: int = ns.stderr_limit
        self.permission_policy: dict[str, Any] = ns.permission_policy


def parse_args(argv: list[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(
        prog="opencode_acp_bridge.py",
        description="MCP stdio bridge exposing direct OpenCode ACP sessions. Runs "
        "one long-lived `opencode acp --pure` child serving multiple "
        "independent agents on a single asyncio loop. Denies ACP "
        "permission requests and launches with deny-all tool access "
        "unless the operator opts in; --allowed-root only routes "
        "agents' cwd and is not a sandbox.",
        epilog="Protocol references: https://agentclientprotocol.com/ and "
        "https://opencode.ai/docs/acp/",
    )
    parser.add_argument(
        "--opencode",
        default="opencode",
        help="OpenCode executable to launch (default: opencode)",
    )
    parser.add_argument(
        "--permission-config",
        dest="permission_policy",
        type=permission_config,
        default={"*": "deny"},
        help="explicit JSON permission object for tool access; default deny-all",
    )
    parser.add_argument(
        "--opencode-arg",
        dest="opencode_args",
        action="append",
        default=None,
        help="argument for the OpenCode child; repeatable and "
        "replaces the default (default: acp --pure)",
    )
    parser.add_argument(
        "--allowed-root",
        dest="allowed_roots",
        action="append",
        required=True,
        type=allowed_root,
        help="existing absolute directory that new agents' cwd "
        "must resolve under; repeatable. Routing only, NOT "
        "a sandbox.",
    )
    parser.add_argument(
        "--max-sessions",
        type=positive_int,
        default=8,
        help="maximum concurrent agents (default: 8)",
    )
    parser.add_argument(
        "--max-output-chars",
        type=positive_int,
        default=200000,
        help="transcript characters retained per agent (default: 200000)",
    )
    parser.add_argument(
        "--startup-timeout",
        type=lambda v: non_negative(v, 0.5),
        default=30.0,
        help="seconds to wait for ACP initialize/session/new (default: 30)",
    )
    parser.add_argument(
        "--prompt-timeout",
        type=lambda v: non_negative(v, 0.0),
        default=600.0,
        help="seconds before a prompt is cancelled; 0 disables (default: 600)",
    )
    parser.add_argument(
        "--cancel-timeout",
        type=lambda v: non_negative(v, 0.5),
        default=10.0,
        help="seconds to wait for a cancelled prompt before "
        "reporting a stall (default: 10)",
    )
    parser.add_argument(
        "--stderr-limit",
        type=positive_int,
        default=64000,
        help="bytes of child stderr retained for diagnostics (default: 64000)",
    )
    parser.add_argument(
        "--version", action="version", version=f"{SERVER_NAME} {SERVER_VERSION}"
    )
    return Config(parser.parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)

    def log(message: str) -> None:
        sys.stderr.write(f"[{SERVER_NAME}] {message}\n")
        sys.stderr.flush()

    bridge = Bridge(cfg, log)
    try:
        asyncio.run(serve(bridge, log))
    except KeyboardInterrupt:
        pass
    finally:
        bridge.request_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
