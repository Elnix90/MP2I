-- User facts
-- memory_upsert_user_fact
INSERT INTO user_facts (fact_id, user_id, fact, source_turn_ids, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(fact_id) DO UPDATE SET
    fact = excluded.fact,
    source_turn_ids = excluded.source_turn_ids,
    updated_at = excluded.updated_at

-- memory_get_user_facts
SELECT fact_id, user_id, fact, source_turn_ids, created_at, updated_at
FROM user_facts
WHERE user_id = ?
ORDER BY updated_at DESC
LIMIT ?

-- memory_clear_user_facts
DELETE FROM user_facts WHERE user_id = ?

-- memory_count_user_fact
SELECT COUNT(*) FROM user_facts WHERE user_id = ?

-- Channel facts
-- memory_upsert_channel_fact
INSERT INTO channel_facts (fact_id, channel_id, fact, source_turn_ids, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(fact_id) DO UPDATE SET
    fact = excluded.fact,
    source_turn_ids = excluded.source_turn_ids,
    updated_at = excluded.updated_at

-- memory_get_channel_facts
SELECT fact_id, channel_id, fact, source_turn_ids, created_at, updated_at
FROM channel_facts
WHERE channel_id = ?
ORDER BY updated_at DESC
LIMIT ?

-- memory_clear_channel_facts
DELETE FROM channel_facts WHERE channel_id = ?
