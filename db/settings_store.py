"""Persistent key-value settings store backed by SQLite.

Replaces the previous JSON-based state files (data/*.json) with a single
`settings` table. It lives in its own database, separate from the colloscope
DB which is regenerated wholesale by generate_colloscope_db.py.

A single long-lived connection is reused (guarded by a lock) instead of
opening a new one on every read/write, keeping the synchronous I/O cost as
low as possible on the async hot paths.
"""

import json
import sqlite3
import threading

from core.config import BOT_STATE_DB_PATH
from db.sql import load
from utils.logger import get_logger

logger = get_logger()

_SCHEMA = load("settings_schema")
_GET_SETTING = load("settings_get")
_SET_SETTING = load("settings_upsert")
_PRAGMA_BUSY = load("settings_pragma_busy")

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        BOT_STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(BOT_STATE_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute(_PRAGMA_BUSY)
        _conn.execute(_SCHEMA)
        _conn.commit()
    return _conn


def get_setting(key: str, default: object = None) -> object:
    try:
        with _lock:
            conn = _connection()
            row = conn.execute(_GET_SETTING, (key,)).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])
    except Exception:
        logger.warning("Failed to read setting %r", key, exc_info=True)
        return default


def set_setting(key: str, value: object) -> None:
    try:
        payload = json.dumps(value)
        with _lock:
            conn = _connection()
            conn.execute(_SET_SETTING, (key, payload))
            conn.commit()
    except Exception:
        logger.warning("Failed to write setting %r", key, exc_info=True)
