-- add_new_ds
INSERT INTO DS (name) VALUES (?) RETURNING id;

-- delete_ds_notes
DELETE FROM NOTES WHERE ds = ?;

-- delete_ds
DELETE FROM DS WHERE id = ?;

-- get_ds_by_name
SELECT id, name FROM DS WHERE name = ?;

-- list_ds
SELECT id, name FROM DS ORDER BY name;
