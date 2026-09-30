-- add_note
INSERT INTO NOTES (user_id, note, ds) VALUES (?, ?, ?) RETURNING id;

-- get_note
SELECT * FROM NOTES WHERE user_id == ? AND ds == ?;

-- remove_note
DELETE FROM NOTES WHERE id = ?;

-- list_notes
SELECT id, user_id, note, ds FROM NOTES ORDER BY ds, user_id;

-- rank_notes
SELECT NOTES.id, NOTES.user_id, NOTES.note, NOTES.ds
FROM NOTES
JOIN DS ON NOTES.ds == DS.id
WHERE ds.id == ?
ORDER BY note DESC;
