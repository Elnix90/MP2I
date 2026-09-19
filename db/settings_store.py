"""Persistent key-value settings store backed by SQLite.

Replaces the previous JSON-based state files (data/*.json) with a single
`settings` table. It lives in its own database, separate from the colloscope
DB which is regenerated wholesale by generate_colloscope_db.py.
"""

import json
import sqlite3

from core.config import BOT_STATE_DB_PATH
from utils.logger import get_logger

logger = get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    BOT_STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(BOT_STATE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute(_SCHEMA)
    return conn


def get_setting(key: str, default: object = None) -> object:
    """Return the JSON-decoded value for `key`, or `default` if missing/invalid."""
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])
    except Exception:
        logger.warning("Failed to read setting %r", key, exc_info=True)
        return default


def set_setting(key: str, value: object) -> None:
    """Store a JSON-serializable `value` under `key`, overwriting any previous one."""
    try:
        payload = json.dumps(value)
        with _connect() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, payload),
            )
    except Exception:
        logger.warning("Failed to write setting %r", key, exc_info=True)