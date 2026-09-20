-- colloscope_schema
CREATE TABLE MATIERES (
    id       INTEGER PRIMARY KEY,
    nom      TEXT NOT NULL
);

CREATE TABLE COLLEURS (
    id       INTEGER PRIMARY KEY,
    nom      TEXT NOT NULL
);

CREATE TABLE PLANNING (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    colleur_id    INTEGER NOT NULL REFERENCES COLLEURS(id),
    matiere_id    INTEGER NOT NULL REFERENCES MATIERES(id),
    salle         TEXT NOT NULL,
    jour_id       INTEGER CHECK (jour_id BETWEEN 0 AND 6),
    creneau_start INTEGER CHECK (creneau_start BETWEEN 0 AND 23),
    semaine       INTEGER NOT NULL CHECK (semaine BETWEEN 1 AND 52),
    groupe        INTEGER NOT NULL CHECK (groupe BETWEEN 1 AND 14),

    UNIQUE (colleur_id, semaine, jour_id, creneau_start)
);

CREATE INDEX idx_planning_colleur ON PLANNING(colleur_id);
CREATE INDEX idx_planning_matiere ON PLANNING(matiere_id);
CREATE INDEX idx_planning_groupe  ON PLANNING(groupe);

-- colleurs_insert
INSERT INTO COLLEURS (id, nom) VALUES (?, ?)

-- matieres_insert
INSERT INTO MATIERES (id, nom) VALUES (?, ?)

-- planning_insert
INSERT INTO PLANNING (colleur_id, matiere_id, salle, jour_id, creneau_start, semaine, groupe)
VALUES (?, ?, ?, ?, ?, ?, ?)

-- colles
SELECT c.nom AS colleur_name,
       m.nom AS matiere,
       p.jour_id,
       p.creneau_start,
       p.salle
FROM planning p
JOIN colleurs c ON c.id = p.colleur_id
JOIN matieres m ON m.id = p.matiere_id
WHERE p.groupe = ?
  AND p.semaine = ?
