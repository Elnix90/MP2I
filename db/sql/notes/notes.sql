-- add_note
INSERT INTO NOTES VALUES (?, ?, ?);

-- remove_note
DELETE FROM NOTES
WHERE id = ?;

-- list_notes
SELECT * FROM NOTES;
