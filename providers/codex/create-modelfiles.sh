#!/usr/bin/env bash
# Creates the qwen3.5-coder ollama Modelfile variant.
# The explorer variant is not needed — qwen3.5:9b defaults already match
# explorer settings (temperature=1.0, presence_penalty=1.5).
set -euo pipefail

ollama create qwen3.5-coder -f - << 'EOF'
FROM qwen3.5:9b
PARAMETER temperature 0.6
PARAMETER top_p 0.95
PARAMETER top_k 20
PARAMETER min_p 0.0
PARAMETER presence_penalty 0.0
PARAMETER repeat_penalty 1.0
PARAMETER num_ctx 65536
EOF

echo "qwen3.5-coder → created"
