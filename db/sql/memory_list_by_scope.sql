SELECT turn_id, user_id, user_name, guild_id, channel_id, thread_id,
       user_content, assistant_content, scope_key, created_at, updated_at
FROM memory_turns
WHERE scope_key = ?
ORDER BY created_at DESC
LIMIT ?


