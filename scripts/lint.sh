#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Format & lint
# ---------------------------------------------------------------------------
echo "Running formatters and linter..."
uv run ruff format . || true
uv run ruff check --fix . || true

if command -v isort >/dev/null 2>&1; then
    echo "Running isort..."
    uv run isort **/*.py || true
else
    echo "⛔ Skipping isort (not installed)"
fi

if command -v removestar >/dev/null 2>&1; then
    echo "Running removestar..."
    uv run removestar . || true
else
    echo "⛔ Skipping removestar (not installed)"
fi

# ---------------------------------------------------------------------------
# 2. Project tree → README
# ---------------------------------------------------------------------------
echo "Updating project tree in README..."
uv run python3 scripts/tree.py

# ---------------------------------------------------------------------------
# 3. PyPI dependencies → README
# ---------------------------------------------------------------------------
echo "Updating dependencies in README..."
uv run python3 scripts/deps.py

# ---------------------------------------------------------------------------
# 4. Env var names → README
# ---------------------------------------------------------------------------
echo "Updating env vars in README..."
uv run python3 scripts/env.py

# ---------------------------------------------------------------------------
# 5. Command documentation → README
# ---------------------------------------------------------------------------
echo "Updating commands in README..."
uv run python3 scripts/gen_cmds.py

echo "✅ All updates completed!"