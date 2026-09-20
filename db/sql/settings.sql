-- Connection / setup
-- settings_pragma_busy
PRAGMA busy_timeout = 5000

-- Schema
-- settings_schema
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)

-- Queries
-- settings_get
SELECT value FROM settings WHERE key = ?

-- settings_upsert
INSERT INTO settings (key, value) VALUES (?, ?)
ON CONFLICT(key) DO UPDATE SET value = excluded.value
