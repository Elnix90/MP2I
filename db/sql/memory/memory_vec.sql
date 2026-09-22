-- memory_create_vec_table
CREATE VIRTUAL TABLE IF NOT EXISTS vec_turns USING vec0(embedding float[{dim}])

-- memory_vec_delete
DELETE FROM vec_turns WHERE rowid = ?

-- memory_vec_insert
INSERT INTO vec_turns(rowid, embedding) VALUES (?, ?)

-- memory_vec_search_all
SELECT v.rowid, v.distance, t.turn_id
FROM (SELECT rowid, distance FROM vec_turns WHERE embedding MATCH ? AND k = ?) v
JOIN memory_turns t ON t.rowid = v.rowid

-- memory_vec_search_scope
SELECT v.rowid, v.distance, t.turn_id
FROM (SELECT rowid, distance FROM vec_turns WHERE embedding MATCH ? AND k = ?) v
JOIN memory_turns t ON t.rowid = v.rowid
WHERE t.scope_key = ?

-- memory_backfill_select
SELECT t.rowid, t.turn_id, t.user_name, t.user_content, t.assistant_content
FROM memory_turns t
LEFT JOIN vec_turns v ON v.rowid = t.rowid
WHERE v.rowid IS NULL
