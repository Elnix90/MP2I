-- Connection / setup
-- memory_pragma_busy
PRAGMA busy_timeout = 5000
pm
-- memory_pragma_wal
PRAGMA journal_mode = WAL

-- memory_table_info
PRAGMA table_info(memory_turns)

-- memory_alter_add_scope_key
ALTER TABLE memory_turns ADD COLUMN scope_key TEXT NOT NULL DEFAULT ''

-- memory_backfill_scope_key
UPDATE memory_turns SET scope_key = CASE
    WHEN thread_id IS NOT NULL THEN 'thread:' || thread_id
    ELSE 'channel:' || channel_id
END WHERE scope_key = ''

-- Turn queries
-- memory_upsert
INSERT INTO memory_turns (turn_id, user_id, user_name, guild_id, channel_id, thread_id, user_content, assistant_content, scope_key, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(turn_id) DO UPDATE SET
    assistant_content = excluded.assistant_content,
    updated_at = excluded.updated_at

-- memory_get_turn
SELECT turn_id, user_id, user_name, guild_id, channel_id, thread_id,
       user_content, assistant_content, scope_key, created_at, updated_at
FROM memory_turns
WHERE turn_id = ?

-- memory_get_turn_by_prefix
SELECT turn_id FROM memory_turns WHERE turn_id LIKE ?

-- memory_get_rowid
SELECT rowid FROM memory_turns WHERE turn_id = ?

-- memory_delete_turn
DELETE FROM memory_turns WHERE turn_id = ?

-- memory_clear_scope
DELETE FROM memory_turns WHERE scope_key = ?

-- memory_list_by_scope
SELECT turn_id, user_id, user_name, guild_id, channel_id, thread_id,
       user_content, assistant_content, scope_key, created_at, updated_at
FROM memory_turns
WHERE scope_key = ?
ORDER BY created_at DESC
LIMIT ?

-- memory_list_recent_all
SELECT * FROM memory_turns ORDER BY created_at DESC LIMIT ?

-- memory_iterate_all
SELECT * FROM memory_turns ORDER BY created_at ASC

-- memory_count_all
SELECT COUNT(*) FROM memory_turns

-- memory_count_scope
SELECT COUNT(*) FROM memory_turns WHERE scope_key = ?

-- memory_delete_all
DELETE FROM memory_turns

-- memory_fts_search_scope
SELECT turn_id FROM memory_turns
WHERE scope_key = ?
AND (user_content LIKE ? OR assistant_content LIKE ?)
ORDER BY created_at DESC
LIMIT ?

-- memory_fts_search_all
SELECT turn_id FROM memory_turns
WHERE user_content LIKE ? OR assistant_content LIKE ?
ORDER BY created_at DESC
LIMIT ?
