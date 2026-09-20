INSERT INTO memory_turns (turn_id, user_id, user_name, guild_id, channel_id, thread_id, user_content, assistant_content, scope_key, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(turn_id) DO UPDATE SET
    assistant_content = excluded.assistant_content,
    updated_at = excluded.updated_at


