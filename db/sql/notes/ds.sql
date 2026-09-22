-- add_new_ds
INSERT INTO DS ?;

-- delete_ds
DELETE FROM NOTES
JOIN DS ON NOTES.ds = DS.id
WHERE ds = ?;
DELETE FROM DS
WHERE id = ?;

-- list_ds
SELECT name FROM DS;
