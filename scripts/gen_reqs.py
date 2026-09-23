import sys
import tomllib
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
REQUIREMENTS = Path("requirements.txt")

if not PYPROJECT.exists():
    sys.exit(0)

data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
deps = sorted(data["project"].get("dependencies", []))
content = "\n".join(deps)
if deps:
    content += "\n"

old = REQUIREMENTS.read_text(encoding="utf-8") if REQUIREMENTS.exists() else ""
if old != content:
    REQUIREMENTS.write_text(content, encoding="utf-8")
    print(f"  requirements.txt regenerated from pyproject.toml ({len(deps)} deps) ✓")
else:
    print(f"  requirements.txt up to date ({len(deps)})")
