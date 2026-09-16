#!/usr/bin/env python3
"""Workflow interface v1. Preview and render by default; apply needs external authority."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
from adapters import AdapterError, FakeAdapter, GitHubEvidence, LinearAdapter


class SnapshotEvidence:
    """Controlled fixture observations. Never accepted for a live mutation."""

    def __init__(self, data):
        self.data = data

    def pull_request(self, repo, number):
        value = self.data.get("%s#%s" % (repo, number))
        if value is None:
            raise AdapterError("fixture_missing", "No fixture observation for required PR")
        return value


def load_packet(packet_path, spec_path=None):
    if not packet_path:
        raise core.CoreError("bad_request", "--packet is required")
    packet = core.load_json(packet_path)
    if spec_path:
        # Only flat scalar metadata is interpreted. Unknown frontmatter stays
        # verbatim in metadata, including nested legacy fields. The source is
        # never rewritten by the importer.
        text = Path(spec_path).read_text()
        metadata = dict(packet.get("spec", {}).get("metadata", {}))
        if text.startswith("---\n"):
            front, sep, body = text[4:].partition("\n---\n")
            if not sep:
                raise core.CoreError("bad_request", "Unterminated spec frontmatter")
            meaningful = []
            bookkeeping_group = False
            metadata["source_frontmatter"] = front
            for line in front.splitlines():
                field, colon, raw = line.partition(":")
                if colon and field and not field[0].isspace():
                    value = raw.strip()
                    try:
                        value = json.loads(value)
                    except ValueError:
                        value = value.strip("\"'")
                    metadata[field] = value
                    bookkeeping_group = field in core.BOOKKEEPING_METADATA
                    if not bookkeeping_group:
                        meaningful.append(line)
                elif not bookkeeping_group:
                    meaningful.append(line)
            metadata["legacy_frontmatter"] = "\n".join(meaningful)
            text = body
        packet.setdefault("spec", {})["markdown"] = text
        packet["spec"]["metadata"] = metadata
        if metadata.get("spec_id"):
            packet["spec"]["spec_id"] = metadata.pop("spec_id")
    return packet


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=["capabilities", "validate", "render", "publish",
                                         "record", "audit", "check-public", "demo"])
    p.add_argument("--packet")
    p.add_argument("--spec", help="Canonical Markdown source; preserve legacy metadata without rewriting it")
    p.add_argument("--config")
    p.add_argument("--state", help="Durable local store for one supervised project")
    p.add_argument("--authority", help="External approval and permission JSON")
    p.add_argument("--request", help="Semantic record request JSON or public text object")
    p.add_argument("--evidence-file", help="Synthetic PR observations; fake adapter only")
    p.add_argument("--adapter", choices=["fake", "linear"], default="fake")
    p.add_argument("--apply", action="store_true", help="Explicitly apply within coherent authority")
    p.add_argument("--destination", choices=["private", "public"], default="private")
    p.add_argument("--workdir", help="New directory for the isolated synthetic demo")
    return p


def adapter_for(args, config):
    if args.adapter == "fake":
        return FakeAdapter(str(Path(args.state).resolve()) + ".fake.json" if args.state else None)
    token = os.environ.get("LINEAR_API_TOKEN")
    if not token:
        raise core.CoreError("authorization_unconfigured", "LINEAR_API_TOKEN is not configured")
    if args.apply and config.get("live_pilot_enabled") is not True:
        raise core.CoreError("activation_required",
                             "A controlled live pilot must be explicitly enabled in operator configuration")
    if args.evidence_file:
        raise core.CoreError("bad_request", "Fixture evidence is restricted to the fake adapter")
    return LinearAdapter(token)


def _evidence(args):
    if args.evidence_file:
        return SnapshotEvidence(core.load_json(args.evidence_file))
    if args.adapter == "linear":
        return GitHubEvidence(os.environ.get("GITHUB_TOKEN"))
    return None


def main(argv=None):
    args = parser().parse_args(argv)
    store = None
    try:
        config = core.load_json(args.config) if args.config else {}
        if args.operation == "audit" and args.apply:
            raise core.CoreError("bad_request", "audit is always read-only; propose repairs for an agent to apply")
        if args.operation == "capabilities":
            result = core.capabilities(config)
            if args.adapter == "linear":
                result["provider"] = adapter_for(args, config).capabilities()
            return emit(result)
        if args.operation == "demo":
            if args.adapter != "fake" or args.apply:
                raise core.CoreError("bad_request", "Demo runs only against an isolated fake; no live adapter or --apply")
            if not args.workdir:
                raise core.CoreError("bad_request", "demo requires --workdir for synthetic files")
            from demo import run_demo
            return emit(run_demo(Path(args.workdir).resolve()))
        if args.operation == "check-public":
            value = core.load_json(args.request) if args.request else {}
            core.assert_public_text_safe(value.get("text", ""), config)
            return emit({"ok": True, "operation": "check-public", "applied": False,
                         "checked": "supplied text only; automatic bot comments need live validation"})
        packet = load_packet(args.packet, args.spec)
        if args.operation == "validate":
            errors = core.collect_validation_errors(packet, config)
            return emit({"ok": not errors, "operation": "validate", "applied": False, "errors": errors,
                         "semantic_digest": core.semantic_digest(packet) if not errors else None}, 2 if errors else 0)
        if args.operation == "render":
            return emit({"ok": True, "operation": "render", "applied": False,
                         "semantic_digest": core.semantic_digest(packet),
                         "markdown": core.render_packet(packet, config)})
        authority = core.load_json(args.authority) if args.authority else {}
        request = core.load_json(args.request) if args.request else {}
        if args.apply:
            if not args.state:
                raise core.CoreError("state_required", "--apply requires --state")
            # Reject missing or mismatched authority before creating any durable state.
            core.require_valid(packet, config)
            core.verify_approval(authority, packet)
            core.verify_permission(authority, packet, "publish" if args.operation == "publish" else "record")
        if args.operation in ("publish", "record") and args.destination != "private":
            core._check_public_destination(packet, config)
        adapter = adapter_for(args, config)
        state_path = str(Path(args.state).resolve()) if args.state else ":memory:"
        store = core.Store(state_path, readonly=not args.apply)
        if args.operation == "publish":
            result = core.publish(packet, config, authority, apply=args.apply, store=store,
                                  adapter=adapter, destination=args.destination)
        elif args.operation == "record":
            result = core.record(packet, config, request, apply=args.apply, store=store, adapter=adapter, authority=authority)
        else:  # audit
            from audit import audit
            result = audit(packet, config, _evidence(args), store=store, adapter=adapter)
        result["evidence_source"] = "controlled_fixture" if args.adapter == "fake" else "live_reads"
        return emit(result, 0 if result.get("ok", True) else 1)
    except (core.CoreError, AdapterError) as exc:
        return emit({"ok": False, "operation": args.operation, "error": {
            "code": exc.code, "message": str(exc), "details": getattr(exc, "details", [])}},
            core.error_exit_code(exc.code))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return emit({"ok": False, "operation": args.operation, "error": {
            "code": "invalid_input", "message": "Malformed or inaccessible input; inspect the declared JSON files",
            "type": type(exc).__name__}}, 2)
    finally:
        if store:
            store.close()


def emit(payload, code=0):
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
