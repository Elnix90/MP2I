SELECT fact_id, channel_id, fact, source_turn_ids, created_at, updated_at
FROM channel_facts
WHERE channel_id = ?
ORDER BY updated_at DESC
LIMIT ?


