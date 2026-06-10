#!/usr/bin/env bash
# Set a plugin's version in both its .claude-plugin and .codex-plugin manifests.
# Usage: scripts/bump-plugin-version.sh <plugin> <version>
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <plugin> <version>" >&2
  exit 1
fi

plugin=$1
version=$2
root=$(cd "$(dirname "$0")/.." && pwd)

if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "version must be semver (X.Y.Z), got: $version" >&2
  exit 1
fi

for manifest in "$root/plugins/$plugin/.claude-plugin/plugin.json" \
  "$root/plugins/$plugin/.codex-plugin/plugin.json"; do
  if [[ ! -f $manifest ]]; then
    echo "missing manifest: $manifest" >&2
    exit 1
  fi
  if ! grep -q '"version":' "$manifest"; then
    echo "no version field in: $manifest" >&2
    exit 1
  fi
  sed -i '' -E "s/\"version\": *\"[^\"]+\"/\"version\": \"$version\"/" "$manifest"
  echo "$manifest -> $version"
done
