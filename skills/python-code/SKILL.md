---
name: python-code
description: Python coding conventions, tooling, and style guide. Auto-loads when writing or reviewing Python code.
---

# Python Conventions

## Tooling

Use `uv` for everything. Do not use pip/venv/poetry directly.

- **Install deps**: `uv sync`
- **Run script**: `uv run <script>.py`
- **Add/remove dep**: `uv add <pkg>` / `uv remove <pkg>`
- **Lint**: `uv run ruff check` (add `--fix` only when asked)
- **Type check**: `uv run ty check`
- **Test**: `uv run pytest`
- **Pre-handoff**: `uv run ruff check && uv run ty check && uv run pytest`

## Style

- Functional for stateless transforms; dataclasses for cohesive state/config
- Use Pydantic (or TypedDict + validators) for validating external data
- Prefer composition over inheritance; keep class hierarchies shallow
- Use `lower_snake_case` for files/dirs (e.g., `routers/user_routes.py`)

## Testing

- Mirror source layout under `tests/`
- Keep fixtures minimal; prefer factory helpers over deep fixture chains
