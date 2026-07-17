"""Best-effort invoking-provider detection, shared by the PostToolUse stamp
hook and the CLI so the harness-specific env-var markers live in exactly one
place (SHOULD-FIX 5: the two used to carry byte-identical copies).
"""

from __future__ import annotations

import os

# ADR-0003 found Claude and Codex indistinguishable via `CLAUDE_PLUGIN_ROOT`
# (both set it); these markers are harness-specific instead.
PROVIDER_ENV_MARKERS = (
    ("claude", "CLAUDECODE"),
    ("codex", "CODEX_SANDBOX_NETWORK_DISABLED"),
    ("gemini", "GEMINI_CLI"),
)


def detect_provider() -> str | None:
    """Best-effort invoking-provider name from harness-set env vars.

    Use when a verb needs to know which agent harness is running -- e.g. the
    stamp hook appending to `authors`, or `file_inbox_item` recording who
    filed a note. Returns None rather than guess when nothing matches, so a
    caller can leave the property alone instead of stamping a wrong provider.
    Do NOT use when you need a hard guarantee of the invoking provider -- this
    is a best-effort env-var sniff, not an authenticated identity.

    Example output:
        'claude'

    Example invocation:
        from llmos_vault.provider import detect_provider
        detect_provider()
    """
    for name, marker in PROVIDER_ENV_MARKERS:
        if os.environ.get(marker):
            return name
    return None
