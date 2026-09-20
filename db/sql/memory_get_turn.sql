SELECT turn_id, user_id, user_name, guild_id, channel_id, thread_id,
       user_content, assistant_content, scope_key, created_at, updated_at
FROM memory_turns
WHERE turn_id = ?


