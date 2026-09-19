"""SQL query loading helpers.

SQL statements live in this directory as `.sql` files so they stay out of
Python code and can be reviewed or edited independently.
"""

from pathlib import Path

_SQL_DIR = Path(__file__).parent


def load(name: str) -> str:
    """Return the stripped contents of the `name.sql` file."""
    return (_SQL_DIR / f"{name}.sql").read_text(encoding="utf-8").strip()
