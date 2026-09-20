SELECT fact_id, user_id, fact, source_turn_ids, created_at, updated_at
FROM user_facts
WHERE user_id = ?
ORDER BY updated_at DESC
LIMIT ?


