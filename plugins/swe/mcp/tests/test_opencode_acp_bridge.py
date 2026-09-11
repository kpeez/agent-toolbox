#!/usr/bin/env python3
"""Offline integration tests for the OpenCode ACP bridge.

These tests drive the real MCP entrypoint (opencode_acp_bridge.py, above the
tests directory) over stdio as a black box. The ACP external boundary is a
fake agent process (fake_opencode_acp.py); nothing here touches the network or
a paid model. Every test builds its own server + fake pair and must shut it
down cleanly on stdin EOF.

Run with:
    python3 plugins/swe/mcp/tests/test_opencode_acp_bridge.py
or:
    python3 -m unittest discover -s plugins/swe/mcp/tests
"""

from __future__ import annotations

import collections
import contextlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, os.pardir, "opencode_acp_bridge.py")
FAKE = os.path.join(HERE, "fake_opencode_acp.py")

WORK_DIR = tempfile.mkdtemp(prefix="acp-bridge-test-work-")

TOOLS = ["spawn_agent", "send_message", "get_agent", "list_agents",
         "wait_agents", "interrupt_agent", "close_agent"]


class McpClient(object):
    """Subprocess driver for one bridge instance (black box)."""

    def __init__(self, extra_args=(), env=None, startup_timeout="10"):
        args = [
            sys.executable, os.path.normpath(SERVER),
            "--opencode", sys.executable,
            "--opencode-arg", FAKE,
            "--allowed-root", WORK_DIR,
            "--startup-timeout", startup_timeout,
        ] + list(extra_args)
        child_env = dict(os.environ)
        # Keep the ambient shell from silently changing the effective policy.
        child_env.pop("OPENCODE_CONFIG_CONTENT", None)
        if env:
            child_env.update(env)
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True,
                                     bufsize=1, env=child_env)
        self.inbox = queue.Queue()
        self.routes = {}
        self.routes_lock = threading.Lock()
        self.out_lock = threading.Lock()
        self.stdout_violations = []
        self.stderr_tail = collections.deque(maxlen=200)
        self.eof = threading.Event()
        self._next_id = 0
        self._id_lock = threading.Lock()
        self._readers = []
        try:
            for target in (self._pump_stdout, self._pump_stderr):
                reader = threading.Thread(target=target, daemon=True)
                reader.start()
                self._readers.append(reader)
        except BaseException:
            try:
                self.proc.kill()
            except OSError:
                pass
            self.proc.wait()
            self.close_streams()
            raise

    # -- plumbing ----------------------------------------------------------

    def _pump_stdout(self):
        try:
            for line in iter(self.proc.stdout.readline, ""):
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    self.stdout_violations.append(
                        "unparseable stdout line: {!r}".format(line[:200]))
                    continue
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    self.stdout_violations.append(
                        "stdout line is not JSON-RPC 2.0: {!r}".format(line[:200]))
                    continue
                if message.get("id") is None:
                    self.inbox.put(message)
                    continue
                with self.routes_lock:
                    target = self.routes.pop(message.get("id"), None)
                if target is None:
                    self.inbox.put(message)
                else:
                    target.put(message)
        except Exception as exc:
            self.stdout_violations.append("stdout pump failed: {!r}".format(exc))
        finally:
            self.eof.set()
            self.inbox.put(None)

    def _pump_stderr(self):
        for line in iter(self.proc.stderr.readline, ""):
            if line.strip():
                self.stderr_tail.append(line)

    def send_raw(self, line):
        with self.out_lock:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()

    def request(self, method, params=None, timeout=20.0):
        with self._id_lock:
            self._next_id += 1
            request_id = self._next_id
        box = queue.Queue()
        with self.routes_lock:
            self.routes[request_id] = box
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        self.send_raw(json.dumps(request))
        return self._await(request_id, box, timeout)

    def _await(self, request_id, box, timeout):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    "timed out waiting for response to {}\nstderr:\n{}".format(
                        request_id, self.stderr_snapshot()))
            try:
                message = box.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                if self.eof.is_set():
                    raise AssertionError(
                        "server exited before responding to {}\nstderr:\n{}".format(
                            request_id, self.stderr_snapshot()))
                continue
            return message

    def stderr_snapshot(self):
        return "".join(self.stderr_tail)

    # -- tool helpers ------------------------------------------------------

    def initialize(self):
        response = self.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "acp-bridge-tests", "version": "0"},
        })
        return response["result"]

    def tools_list(self):
        return self.request("tools/list")["result"]["tools"]

    def call(self, name, arguments=None, timeout=30.0):
        """Tool call returning the parsed structured result."""
        response = self.request("tools/call",
                                {"name": name, "arguments": arguments or {}},
                                timeout=timeout)
        return response["result"]

    def call_expect_error(self, name, arguments=None, timeout=30.0):
        result = self.call(name, arguments, timeout=timeout)
        if not result.get("isError"):
            raise AssertionError("expected isError for {} with {}:\n{}".format(
                name, arguments, json.dumps(result)[:500]))
        return result["content"][0]["text"]

    def call_expect_ok(self, name, arguments=None, timeout=30.0):
        result = self.call(name, arguments, timeout=timeout)
        if result.get("isError"):
            raise AssertionError("unexpected tool error for {} {}:\n{}".format(
                name, arguments, result["content"][0]["text"]))
        if "structuredContent" in result:
            return result["structuredContent"]
        return json.loads(result["content"][0]["text"])

    # -- shutdown ----------------------------------------------------------

    def close_streams(self):
        for reader in self._readers:
            reader.join(timeout=2)
            if reader.is_alive():
                raise AssertionError("MCP reader did not stop after child exit")
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()

    def finish(self):
        """Close stdin and require a clean, bounded server exit."""
        try:
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            code = self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
            raise AssertionError("server did not exit after stdin EOF\nstderr:\n" +
                                 self.stderr_snapshot())
        if code != 0:
            raise AssertionError(
                "server exited with {} (expected 0)\nstderr:\n{}".format(
                    code, self.stderr_snapshot()))
        return code

    def abort(self):
        """Best-effort teardown for a failed test, without hiding the failure."""
        try:
            self.proc.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            self.proc.terminate()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            pass
        try:
            self.proc.kill()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


@contextlib.contextmanager
def mcp_client(extra_args=(), env=None):
    """Yield a live client; assert clean EOF on success, never leak on failure."""
    client = McpClient(extra_args, env=env)
    try:
        yield client
    except BaseException:
        client.abort()
        raise
    else:
        client.finish()
        if client.stdout_violations:
            raise AssertionError(
                "MCP stdout violations: {}".format(client.stdout_violations[:5]))
    finally:
        client.close_streams()


def spawn(client, prompt, extras=None):
    arguments = {"prompt": prompt, "cwd": WORK_DIR}
    if extras:
        arguments.update(extras)
    return client.call_expect_ok("spawn_agent", arguments)


def wait_idle(client, agent_ids, timeout=30.0):
    return client.call_expect_ok(
        "wait_agents", {"agent_ids": agent_ids, "timeout": timeout},
        timeout=timeout + 15)


def share_is_disabled(value):
    if value is False:
        return True
    return isinstance(value, str) and value.lower() == "disabled"


def _build_entry(policy):
    """Return the forced build-mode mapping, if the policy nests one."""
    for container in (policy.get("agent"), policy.get("mode")):
        if isinstance(container, dict) and isinstance(container.get("build"), dict):
            return container["build"]
    return None


def build_mode_is_forced(policy):
    if policy.get("mode") == "build":
        return True
    if policy.get("default_agent") == "build":
        return True
    if isinstance(policy.get("mode"), dict) and "build" in policy["mode"]:
        return True
    if isinstance(policy.get("agent"), dict) and "build" in policy["agent"]:
        return True
    return False


def effective_permission(policy):
    """Permission policy, at top level or on the forced build mode."""
    if isinstance(policy.get("permission"), dict):
        return policy["permission"]
    build = _build_entry(policy)
    if build is not None and isinstance(build.get("permission"), dict):
        return build["permission"]
    return policy.get("permission")


def effective_tools(policy):
    if isinstance(policy.get("tools"), dict):
        return policy["tools"]
    build = _build_entry(policy)
    if build is not None and isinstance(build.get("tools"), dict):
        return build["tools"]
    return None


class BridgeToolTests(unittest.TestCase):
    """Each test builds its own server + fake ACP pair."""

    def get_agent(self, client, agent_id, cursor=None):
        arguments = {"agent_id": agent_id}
        if cursor is not None:
            arguments["cursor"] = cursor
        return client.call_expect_ok("get_agent", arguments)

    def read_policy(self, client, agent):
        wait_idle(client, [agent["agent_id"]])
        text = self.get_agent(client, agent["agent_id"])["output"]["text"]
        marker = "policy:"
        index = text.rfind(marker)
        self.assertGreaterEqual(index, 0, text)
        return json.loads(text[index + len(marker):])

    # -- handshake ---------------------------------------------------------

    def test_initialize_and_tools_list(self):
        with mcp_client() as client:
            info = client.initialize()
            self.assertEqual(info["serverInfo"]["name"], "opencode-acp-bridge")
            self.assertEqual(client.request("ping")["result"], {})
            names = sorted(tool["name"] for tool in client.tools_list())
            self.assertEqual(names, sorted(TOOLS))

    def test_help_documents_permission_config_and_routing(self):
        proc = subprocess.run([sys.executable, os.path.normpath(SERVER), "--help"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--permission-config", proc.stdout)
        self.assertIn("--allowed-root", proc.stdout)
        self.assertIn("sandbox", proc.stdout)
        proc = subprocess.run(
            [sys.executable, os.path.normpath(SERVER), "--allowed-root", "."],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("absolute path", proc.stderr)

    def test_malformed_and_unknown_requests_do_not_kill_server(self):
        with mcp_client() as client:
            client.send_raw("this is not json")
            parse_error = client.inbox.get(timeout=10)
            self.assertEqual(parse_error["error"]["code"], -32700)
            self.assertIsNone(parse_error["id"])
            unknown = client.request("bogus/method", {})
            self.assertEqual(unknown["error"]["code"], -32601)
            self.assertEqual(client.request("ping")["result"], {})

    # -- parallel isolation and followups ----------------------------------

    def test_parallel_agents_isolate_cwd_and_output(self):
        dir_a = os.path.join(WORK_DIR, "iso-a")
        dir_b = os.path.join(WORK_DIR, "iso-b")
        os.makedirs(dir_a, exist_ok=True)
        os.makedirs(dir_b, exist_ok=True)
        with mcp_client() as client:
            client.initialize()
            first = spawn(client, "alpha", extras={"cwd": dir_a})
            second = spawn(client, "beta", extras={"cwd": dir_b})
            results = wait_idle(client, [first["agent_id"], second["agent_id"]])
            self.assertFalse(results["timed_out"])
            view_a = self.get_agent(client, first["agent_id"])
            view_b = self.get_agent(client, second["agent_id"])
            self.assertNotEqual(first["session_id"], second["session_id"])
            self.assertIn("echo:alpha", view_a["output"]["text"])
            self.assertIn("cwd=" + os.path.realpath(dir_a), view_a["output"]["text"])
            self.assertIn("session=" + first["session_id"], view_a["output"]["text"])
            self.assertIn("echo:beta", view_b["output"]["text"])
            self.assertIn("cwd=" + os.path.realpath(dir_b), view_b["output"]["text"])
            self.assertNotIn(dir_b, view_a["output"]["text"])

    def test_followup_reuses_the_same_session(self):
        with mcp_client() as client:
            client.initialize()
            agent = spawn(client, "first")
            wait_idle(client, [agent["agent_id"]])
            follow = client.call_expect_ok(
                "send_message", {"agent_id": agent["agent_id"], "prompt": "second"})
            self.assertEqual(follow["state"], "running")
            wait_idle(client, [agent["agent_id"]])
            view = self.get_agent(client, agent["agent_id"])
            self.assertEqual(view["session_id"], agent["session_id"])
            self.assertEqual(view["state"], "idle")
            self.assertEqual(view["stop_reason"], "end_turn")
            self.assertIn("echo:first", view["output"]["text"])
            self.assertIn("echo:second", view["output"]["text"])

    # -- concurrent sends are rejected, never queued -----------------------

    def test_concurrent_sends_are_rejected_not_queued(self):
        with mcp_client() as client:
            client.initialize()
            agent = spawn(client, "idle")
            wait_idle(client, [agent["agent_id"]])
            outcomes = []
            lock = threading.Lock()

            def send():
                try:
                    result = client.call_expect_ok(
                        "send_message",
                        {"agent_id": agent["agent_id"], "prompt": "[[slow]]"},
                        timeout=30)
                    with lock:
                        outcomes.append(("ok", result))
                except BaseException as exc:
                    with lock:
                        outcomes.append(("error", str(exc)))

            threads = [threading.Thread(target=send) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
            kinds = sorted(kind for kind, _ in outcomes)
            self.assertEqual(kinds, ["error", "ok"], outcomes)
            rejected = [value for kind, value in outcomes if kind == "error"]
            self.assertIn("running", rejected[0])
            client.call_expect_ok("interrupt_agent", {"agent_id": agent["agent_id"]})
            wait_idle(client, [agent["agent_id"]])

    # -- bounded tail output and cursors -----------------------------------

    def test_tail_output_and_cursor_with_oversize_chunk(self):
        with mcp_client(["--max-output-chars", "1000"]) as client:
            client.initialize()
            agent = spawn(client, "[[long]]")
            wait_idle(client, [agent["agent_id"]])
            output = self.get_agent(client, agent["agent_id"])["output"]
            self.assertTrue(output["truncated"])
            self.assertEqual(output["total_chars"], 30000)
            self.assertEqual(output["dropped_chars"], 29000)
            self.assertEqual(output["next_cursor"], 30000)
            self.assertEqual(output["text"], "C" * 1000)
            self.assertFalse(output["has_more"])
            tail = self.get_agent(client, agent["agent_id"], cursor=29000)
            self.assertEqual(tail["output"]["text"], "C" * 1000)
            beyond = self.get_agent(client, agent["agent_id"], cursor=30000)
            self.assertEqual(beyond["output"]["text"], "")

    # -- 24 concurrent waits stay responsive -------------------------------

    def test_many_concurrent_waits_keep_status_and_interrupt_responsive(self):
        with mcp_client(["--max-sessions", "24", "--prompt-timeout", "0"]) as client:
            client.initialize()
            agents = [spawn(client, "[[hold]]") for _ in range(24)]
            ids = [agent["agent_id"] for agent in agents]
            results = {}
            errors = []
            lock = threading.Lock()

            def waiter(index):
                try:
                    value = wait_idle(client, [ids[index]], timeout=30)
                    with lock:
                        results[index] = value
                except BaseException as exc:
                    with lock:
                        errors.append(exc)

            threads = [threading.Thread(target=waiter, args=(i,))
                       for i in range(24)]
            for thread in threads:
                thread.start()
            time.sleep(0.5)

            start = time.monotonic()
            snapshot = self.get_agent(client, ids[0])
            self.assertLess(time.monotonic() - start, 3.0,
                            "get_agent blocked behind 24 waits")
            self.assertEqual(snapshot["state"], "running")
            start = time.monotonic()
            listing = client.call_expect_ok("list_agents")
            self.assertLess(time.monotonic() - start, 3.0,
                            "list_agents blocked behind 24 waits")
            self.assertEqual(listing["count"], 24)

            start = time.monotonic()
            for agent_id in ids:
                interrupt = client.call_expect_ok(
                    "interrupt_agent", {"agent_id": agent_id})
                self.assertTrue(interrupt["interrupt_requested"])
            self.assertLess(time.monotonic() - start, 15.0,
                            "interrupt blocked behind 24 waits")

            for thread in threads:
                thread.join(timeout=30)
            self.assertFalse(errors, errors[:1])
            self.assertEqual(len(results), 24)
            for index in range(24):
                self.assertFalse(results[index]["timed_out"])
                entry = results[index]["agents"][ids[index]]
                self.assertEqual(entry["state"], "idle")
                self.assertEqual(entry["stop_reason"], "cancelled")

    # -- prompt timeout recovery -------------------------------------------

    def test_prompt_timeout_recovers_without_stale_watchdog(self):
        with mcp_client(["--prompt-timeout", "1", "--cancel-timeout", "5"]) as client:
            client.initialize()
            agent = spawn(client, "[[slow]]")
            results = wait_idle(client, [agent["agent_id"]], timeout=15)
            entry = results["agents"][agent["agent_id"]]
            self.assertEqual(entry["state"], "idle")
            self.assertEqual(entry["stop_reason"], "cancelled")
            self.assertIn("prompt-timeout", entry["error"])
            follow = client.call_expect_ok(
                "send_message", {"agent_id": agent["agent_id"], "prompt": "recovered"})
            self.assertEqual(follow["state"], "running")
            results = wait_idle(client, [agent["agent_id"]], timeout=15)
            entry = results["agents"][agent["agent_id"]]
            self.assertEqual(entry["state"], "idle")
            self.assertEqual(entry["stop_reason"], "end_turn")
            self.assertIsNone(entry["error"])
            text = self.get_agent(client, agent["agent_id"])["output"]["text"]
            self.assertIn("echo:recovered", text)

    # -- slots: limit, reuse, stalled cancel --------------------------------

    def test_session_limit_and_slot_reuse_after_close(self):
        with mcp_client(["--max-sessions", "2"]) as client:
            client.initialize()
            first = spawn(client, "one")
            second = spawn(client, "[[hold]]")
            error = client.call_expect_error(
                "spawn_agent", {"prompt": "three", "cwd": WORK_DIR})
            self.assertIn("session limit", error)
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 2)
            closed = client.call_expect_ok(
                "close_agent", {"agent_id": first["agent_id"]})
            self.assertTrue(closed["closed"])
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 1)
            third = spawn(client, "three")
            wait_idle(client, [third["agent_id"]])
            client.call_expect_ok("interrupt_agent", {"agent_id": second["agent_id"]})
            wait_idle(client, [second["agent_id"]])

    def test_stalled_cancel_keeps_slot_and_refuses_new_prompts(self):
        with mcp_client(["--max-sessions", "1", "--prompt-timeout", "1",
                         "--cancel-timeout", "1"]) as client:
            client.initialize()
            agent = spawn(client, "[[stall-cancel]]")
            results = wait_idle(client, [agent["agent_id"]], timeout=15)
            entry = results["agents"][agent["agent_id"]]
            self.assertEqual(entry["state"], "failed")
            self.assertIn("cancel", str(entry["error"]))
            send_error = client.call_expect_error(
                "send_message", {"agent_id": agent["agent_id"], "prompt": "again"})
            self.assertIn("failed", send_error)
            closed = client.call_expect_ok(
                "close_agent", {"agent_id": agent["agent_id"]})
            self.assertFalse(closed["closed"])
            self.assertFalse(closed["acp_session_closed"])
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 1)
            spawn_error = client.call_expect_error(
                "spawn_agent", {"prompt": "new", "cwd": WORK_DIR})
            self.assertIn("session limit", spawn_error)

    # -- child death --------------------------------------------------------

    def test_child_death_fails_idle_and_running_sessions(self):
        with mcp_client() as client:
            client.initialize()
            idle_agent = spawn(client, "stable")
            wait_idle(client, [idle_agent["agent_id"]])
            self.assertEqual(
                self.get_agent(client, idle_agent["agent_id"])["state"], "idle")
            crash_agent = spawn(client, "[[crash]]")
            results = wait_idle(client, [crash_agent["agent_id"]], timeout=20)
            self.assertEqual(results["agents"][crash_agent["agent_id"]]["state"],
                             "failed")
            listing = client.call_expect_ok("list_agents")
            self.assertEqual(listing["count"], 2)
            self.assertTrue(all(agent["state"] == "failed"
                                for agent in listing["agents"]), listing["agents"])
            idle_view = self.get_agent(client, idle_agent["agent_id"])
            self.assertEqual(idle_view["state"], "failed")
            self.assertIn("exited", str(idle_view["error"]))
            spawn_error = client.call_expect_error(
                "spawn_agent", {"prompt": "again", "cwd": WORK_DIR})
            self.assertTrue("exited" in spawn_error or "restart" in spawn_error,
                            spawn_error)
            closed = client.call_expect_ok(
                "close_agent", {"agent_id": idle_agent["agent_id"]})
            self.assertTrue(closed["closed"])
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 1)

    # -- grouped model selection -------------------------------------------

    def test_grouped_model_selection_applies_or_rejects(self):
        with mcp_client() as client:
            client.initialize()
            picked = spawn(client, "model check", extras={"model": "fake/grouped"})
            wait_idle(client, [picked["agent_id"]])
            view = self.get_agent(client, picked["agent_id"])
            self.assertEqual(view["model"], "fake/grouped")
            self.assertIn("model=fake/grouped", view["output"]["text"])
            unknown = client.call_expect_error(
                "spawn_agent",
                {"prompt": "x", "cwd": WORK_DIR, "model": "fake/nope"})
            self.assertIn("fake/grouped", unknown)
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 1)

    # -- permissions --------------------------------------------------------

    def test_permission_request_denied_and_visible(self):
        with mcp_client() as client:
            client.initialize()
            agent = spawn(client, "[[permission]]")
            wait_idle(client, [agent["agent_id"]])
            view = self.get_agent(client, agent["agent_id"])
            self.assertEqual(len(view["blocked_reasons"]), 1)
            self.assertIn("reject", view["blocked_reasons"][0])
            self.assertIn("call-1", view["blocked_reasons"][0])
            self.assertIn("denied via reject-once", view["output"]["text"])
            self.assertNotIn("ALLOWED", view["output"]["text"])

    # -- cwd routing --------------------------------------------------------

    def test_cwd_validation_and_symlink_root_routing(self):
        inside = os.path.join(WORK_DIR, "route-real")
        os.makedirs(inside, exist_ok=True)
        link = os.path.join(WORK_DIR, "route-link")
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(inside, link)
        outside = tempfile.mkdtemp(prefix="acp-bridge-outside-")
        outside_link = os.path.join(WORK_DIR, "route-out")
        if os.path.lexists(outside_link):
            os.remove(outside_link)
        os.symlink(outside, outside_link)
        try:
            with mcp_client() as client:
                client.initialize()
                error = client.call_expect_error(
                    "spawn_agent", {"prompt": "go", "cwd": "relative/path"})
                self.assertIn("absolute", error)
                missing = os.path.join(WORK_DIR, "no-such-dir")
                error = client.call_expect_error(
                    "spawn_agent", {"prompt": "go", "cwd": missing})
                self.assertIn("existing directory", error)
                error = client.call_expect_error(
                    "spawn_agent", {"prompt": "go", "cwd": outside_link})
                self.assertIn("allowed-root", error)
                agent = spawn(client, "routed", extras={"cwd": link})
                wait_idle(client, [agent["agent_id"]])
                text = self.get_agent(client, agent["agent_id"])["output"]["text"]
                self.assertIn("cwd=" + os.path.realpath(link), text)
                self.assertEqual(client.call_expect_ok("list_agents")["count"], 1)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    # -- effective child policy --------------------------------------------

    def test_default_child_config_denies_tools_and_disables_share(self):
        inherited = {
            "model": "opencode/inherited",
            "permission": {"*": "allow", "bash": "allow"},
            "tools": {"bash": True},
            "share": "auto",
            "mode": "plan",
        }
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(inherited)}
        with mcp_client(env=env) as client:
            client.initialize()
            policy = self.read_policy(client, spawn(client, "[[policy]]"))
            self.assertEqual(policy.get("model"), "opencode/inherited")
            permission = effective_permission(policy)
            self.assertIsInstance(permission, dict, policy)
            self.assertEqual(permission.get("*"), "deny")
            self.assertNotIn("allow", json.dumps(permission))
            self.assertNotIn("true", json.dumps(effective_tools(policy) or {}).lower())
            self.assertTrue(share_is_disabled(policy.get("share")),
                            policy.get("share"))
            self.assertTrue(build_mode_is_forced(policy), policy)

    def test_permission_config_flag_applies_operator_object(self):
        operator = {
            "*": "deny",
            "read": {"/allowed/**": "allow"},
            "task": "allow",
        }
        effective = dict(operator)
        effective.pop("task")
        effective["task"] = "deny"
        path = os.path.join(WORK_DIR, "operator-permission.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(operator, handle)
        inherited = {
            "model": "opencode/keep",
            "permission": {"*": "allow"},
            "tools": {"task": True},
            "agent": {
                "custom": {
                    "permission": {"*": "allow"},
                    "tools": {"task": True},
                }
            },
            "share": "auto",
            "mode": "plan",
        }
        env = {"OPENCODE_CONFIG_CONTENT": json.dumps(inherited)}
        with mcp_client(["--permission-config", path], env=env) as client:
            client.initialize()
            policy = self.read_policy(client, spawn(client, "[[policy]]"))
            self.assertEqual(effective_permission(policy), effective)
            self.assertEqual(list(effective_permission(policy))[-1], "task")
            self.assertEqual(policy.get("tools"), {"task": False})
            for agent in policy["agent"].values():
                self.assertEqual(agent.get("permission"), effective)
                self.assertEqual(agent.get("tools"), {"task": False})
            self.assertEqual(policy.get("model"), "opencode/keep")
            self.assertTrue(share_is_disabled(policy.get("share")),
                            policy.get("share"))
            self.assertTrue(build_mode_is_forced(policy), policy)

        wildcard_path = os.path.join(WORK_DIR, "wildcard-permission.json")
        with open(wildcard_path, "w", encoding="utf-8") as handle:
            json.dump({"*": "deny", "t*": "allow"}, handle)
        proc = subprocess.run(
            [
                sys.executable,
                os.path.normpath(SERVER),
                "--allowed-root",
                WORK_DIR,
                "--permission-config",
                wildcard_path,
            ],
            input="",
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("can match task", proc.stderr)

    # -- startup failure ----------------------------------------------------

    def test_startup_failure_is_reported_and_server_stays_alive(self):
        with mcp_client(["--opencode", os.path.join(WORK_DIR, "no-such-binary")]) as client:
            error = client.call_expect_error(
                "spawn_agent", {"prompt": "go", "cwd": WORK_DIR})
            self.assertIn("startup", error.lower())
            self.assertEqual(client.request("ping")["result"], {})
            self.assertEqual(client.call_expect_ok("list_agents")["count"], 0)

    # -- clean EOF shutdown -------------------------------------------------

    def test_eof_shutdown_while_a_turn_runs_is_clean(self):
        client = McpClient(["--prompt-timeout", "0"])
        try:
            client.initialize()
            spawn(client, "[[hold]]")
            self.assertEqual(client.finish(), 0)
        except BaseException:
            client.abort()
            raise
        finally:
            client.close_streams()


def tearDownModule():
    shutil.rmtree(WORK_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
