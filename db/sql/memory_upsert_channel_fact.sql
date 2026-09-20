INSERT INTO channel_facts (fact_id, channel_id, fact, source_turn_ids, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(fact_id) DO UPDATE SET
    fact = excluded.fact,
    source_turn_ids = excluded.source_turn_ids,
    updated_at = excluded.updated_at


