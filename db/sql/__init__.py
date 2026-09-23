"""SQL query loading helpers.

SQL statements live in this directory as `.sql` files so they stay out of
Python code and can be reviewed or edited independently.

Queries can be stored either as a single statement in a dedicated
`{name}.sql` file, or as a named section inside a logical group file:

    -- memory_upsert
    INSERT INTO memory_turns ...;

`load("name")` first looks for `name.sql`, then scans group files for a
`-- name` section header (a line containing only the name).
"""

import re
from pathlib import Path

_SQL_DIR = Path(__file__).parent
_SECTION_HEADER = re.compile(r"^--\s*([a-z][a-z0-9_]*)\s*$")

_cache: dict[str, str] = {}


def load(name: str) -> str:
    direct = _SQL_DIR / f"{name}.sql"
    if direct.exists():
        return direct.read_text(encoding="utf-8").strip()

    if name in _cache:
        return _cache[name]

    for path in sorted(_SQL_DIR.rglob("*.sql")):
        sql = _section(path, name)
        if sql is not None:
            _cache[name] = sql
            return sql

    raise FileNotFoundError(f"No SQL found for {name!r}")


def _section(path: Path, name: str) -> str | None:
    current: str | None = None
    buf: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _SECTION_HEADER.match(line)
        if m:
            if current == name:
                return "\n".join(buf).strip()
            current = m.group(1)
            buf = []
        elif current == name:
            buf.append(line)
    if current == name:
        return "\n".join(buf).strip()
    return None
