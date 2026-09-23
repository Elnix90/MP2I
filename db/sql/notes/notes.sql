-- add_note
INSERT INTO NOTES (user_id, note, ds) VALUES (?, ?, ?) RETURNING id;

-- remove_note
DELETE FROM NOTES WHERE id = ?;

-- list_notes
SELECT id, user_id, note, ds FROM NOTES ORDER BY ds, user_id;
