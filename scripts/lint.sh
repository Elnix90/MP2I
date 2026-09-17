#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Format code (run only if available)
# ---------------------------------------------------------------------------
echo "Running formatters if available..."
if command -v ruff >/dev/null 2>&1; then
    echo "1️⃣  Running ruff format..."
    ruff format . || true
else
    echo " ⛔ Skipping ruff (not installed)"
    echo "Install it with `uv tool install ruff`"
fi
if command -v isort >/dev/null 2>&1; then
    echo "2️⃣  Running isort..."
    isort **/*.py || true
else
    echo " ⛔ Skipping isort (not installed)"
    echo "Install it with `uv tool install isort`"
fi
if command -v removestar >/dev/null 2>&1; then
    echo "3️⃣  Running removestar..."
    removestar . || true
else
    echo " ⛔ Skipping removestar (not installed)"
    echo "Install it with `uv tool install removestar`"
fi

# ---------------------------------------------------------------------------
# 2. Project tree → stdout + README (between <!-- TREE-START --> / <!-- TREE-END -->)
# ---------------------------------------------------------------------------
python3 scripts/tree.py
# ---------------------------------------------------------------------------
# 3. PyPI dependencies → README (between <!--DEPS-START--> / <!--DEPS-END-->)
# ---------------------------------------------------------------------------
python3 scripts/deps.py
# ---------------------------------------------------------------------------
# 4. Env var names → README (between <!--ENV-START--> / <!--ENV-END-->)
# ---------------------------------------------------------------------------
python3 scripts/env.py
# ---------------------------------------------------------------------------
# 5. Command documentation → README (between <!-- COMMANDS-START --> / <!-- COMMANDS-END -->)
# ---------------------------------------------------------------------------
python3 scripts/cmds.py

echo "✅ All updates completed!"
