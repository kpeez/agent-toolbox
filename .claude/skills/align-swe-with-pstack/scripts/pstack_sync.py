#!/usr/bin/env python3
"""Compare swe with upstream pstack through the manifest in upstream.json."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
MANIFEST = SKILL / "upstream.json"
REPO = SKILL.parent.parent.parent


def git(*args, cwd, check=True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True
    )
    if check and result.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result


def load():
    return json.loads(MANIFEST.read_text())


def item_for(manifest, path):
    """Return the item for an upstream path: an exact match, else the longest
    directory prefix that ends in '/'."""
    exact = [i for i in manifest["items"] if i["upstream"] == path]
    if exact:
        return exact[0]
    dirs = [
        i
        for i in manifest["items"]
        if i["upstream"].endswith("/") and path.startswith(i["upstream"])
    ]
    return max(dirs, key=lambda i: len(i["upstream"]), default=None)


def upstream(args, manifest):
    clone = Path(args.upstream)
    if (clone / ".git").exists():
        git("fetch", "--quiet", "origin", cwd=clone)
    else:
        if not clone.parent.is_dir():
            sys.exit(f"{clone.parent} does not exist. Create it or pass --upstream.")
        git(
            "clone", "--quiet", "--filter=blob:none", "--no-checkout",
            manifest["repo"], str(clone), cwd=REPO,
        )
    return clone


def resolve(clone, ref):
    return git("rev-parse", ref + "^{commit}", cwd=clone).stdout.strip()


def changes(clone, manifest, to):
    """Yield (status, upstream path, item) for each pstack file that changed
    between the pinned commit and `to`. Renames come as delete plus add."""
    prefix = manifest["path"] + "/"
    out = git(
        "diff", "--no-renames", "--name-status", manifest["commit"], to,
        "--", manifest["path"], cwd=clone,
    ).stdout
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        rel = path.removeprefix(prefix)
        yield status, rel, item_for(manifest, rel)


def show(clone, rev, path):
    result = git("show", f"{rev}:{path}", cwd=clone, check=False)
    return result.stdout if result.returncode == 0 else None


def cmd_status(args):
    manifest = load()
    clone = upstream(args, manifest)
    to = resolve(clone, args.to)
    pin = manifest["commit"]
    print(f"pin  {pin}\nto   {to}\n")
    log = git(
        "log", "--oneline", f"{pin}..{to}", "--", manifest["path"], cwd=clone
    ).stdout
    print("commits:\n" + (log or "  none\n"))
    groups = {}
    for status, rel, item in changes(clone, manifest, to):
        key = "new" if status == "A" and not item else (
            item["class"] if item else "unmapped"
        )
        groups.setdefault(key, []).append((status, rel, item))
    for key in ("copied", "modified", "new", "unmapped", "dropped"):
        for status, rel, item in groups.get(key, []):
            local = ", ".join(item.get("local", [])) if item else ""
            print(f"{key:9} {status} {rel}" + (f"  ->  {local}" if local else ""))
            if args.diff and key in ("modified", "new", "unmapped"):
                path = f"{manifest['path']}/{rel}"
                print(git("diff", pin, to, "--", path, cwd=clone).stdout)
    if not groups:
        print("no pstack changes")


def cmd_merge(args):
    """Three-way merge upstream changes into each copied file. Write a file only
    when its merge is clean."""
    manifest = load()
    clone = upstream(args, manifest)
    to = resolve(clone, args.to)
    pin = manifest["commit"]
    conflicts = 0
    for status, rel, item in changes(clone, manifest, to):
        if not item or item["class"] != "copied":
            continue
        local = REPO / item["local"][0]
        path = f"{manifest['path']}/{rel}"
        if status != "M":
            print(f"review   {status} {rel}: not a plain change")
            conflicts += 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            base, theirs = Path(tmp, "base"), Path(tmp, "theirs")
            base.write_text(show(clone, pin, path))
            theirs.write_text(show(clone, to, path))
            result = subprocess.run(
                ["git", "merge-file", "-p", str(local), str(base), str(theirs)],
                capture_output=True, text=True,
            )
        if result.returncode == 0:
            local.write_text(result.stdout)
            print(f"merged   {item['local'][0]}")
        else:
            print(f"conflict {item['local'][0]}: review it as modified")
            conflicts += 1
    sys.exit(1 if conflicts else 0)


def cmd_check(args):
    """Check that the manifest covers every pinned pstack file, that each local
    path exists, and that the README credit names the pin."""
    manifest = load()
    clone = upstream(args, manifest)
    pin = manifest["commit"]
    prefix = manifest["path"] + "/"
    files = git(
        "ls-tree", "-r", "--name-only", pin, manifest["path"], cwd=clone
    ).stdout.split()
    problems = []
    for path in files:
        if not item_for(manifest, path.removeprefix(prefix)):
            problems.append(f"no manifest item: {path}")
    pinned = {p.removeprefix(prefix) for p in files}
    for item in manifest["items"]:
        up = item["upstream"]
        if up.endswith("/"):
            if not any(p.startswith(up) for p in pinned):
                problems.append(f"no pinned files under: {up}")
        elif up not in pinned:
            problems.append(f"not at pin: {up}")
        if item["class"] not in ("copied", "modified", "dropped"):
            problems.append(f"bad class: {up}")
        local = item.get("local", [])
        if item["class"] == "dropped" and local:
            problems.append(f"dropped item has local paths: {up}")
        if item["class"] == "copied" and len(local) != 1:
            problems.append(f"copied item needs one local path: {up}")
        if item["class"] == "modified" and not local:
            problems.append(f"modified item needs local paths: {up}")
        problems += [f"missing local: {p}" for p in local if not (REPO / p).exists()]
    if pin not in (REPO / "README.md").read_text():
        problems.append("README.md Credits does not link the pinned commit")
    print("\n".join(problems) or f"ok: {len(files)} pinned files covered")
    sys.exit(1 if problems else 0)


def cmd_pin(args):
    """Move the pin to a new commit and update the README credit link."""
    manifest = load()
    clone = upstream(args, manifest)
    new, old = resolve(clone, args.to), manifest["commit"]
    manifest["commit"] = new
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    readme = REPO / "README.md"
    readme.write_text(readme.read_text().replace(old, new))
    print(f"pinned {new}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--upstream",
        default=str(REPO / "artifacts" / "pstack-upstream"),
        help="local clone of the upstream repo (cloned on first use)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="list upstream changes since the pin")
    status.add_argument("--to", default="origin/main")
    status.add_argument(
        "--diff", action="store_true",
        help="print the upstream diff of each modified, new, or unmapped file",
    )
    merge = sub.add_parser("merge", help="merge upstream changes into copied files")
    merge.add_argument("--to", default="origin/main")
    sub.add_parser("check", help="validate the manifest against the pin")
    pin = sub.add_parser("pin", help="move the pin and the README credit link")
    pin.add_argument("--to", default="origin/main")
    args = parser.parse_args()
    {"status": cmd_status, "merge": cmd_merge, "check": cmd_check, "pin": cmd_pin}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
