"""Génère colloscope.db à partir du Colloscope MP2I S1 2026/2027.

Un créneau est étalé en un enregistrement PLANNING par (semaine, groupe).
Le schéma est normalisé : COLLEURS, MATIERES et PLANNING.
Les créneaux du bloc du haut (Ratte/Mensah/Gaudillat) sont des colles d'Anglais.
"""

from core.config import DB_PATH
from db.init.colleurs import COLLEURS
from db.init.rows import ROWS
from db.init.subjects import MATIERES
from db.sql_requests import get_db_connection


def main() -> None:
    if DB_PATH is None:
        return
    if DB_PATH.exists():
        DB_PATH.unlink()
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.executescript(
            """
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
            """
        )

        for colleur_id, colleur_name in COLLEURS.items():
            cur.execute(
                """
                INSERT INTO COLLEURS (id, nom) VALUES (?, ?)
                """,
                (colleur_id, colleur_name),
            )

        for matiere_id, matiere_name in MATIERES.items():
            cur.execute(
                """
                INSERT INTO MATIERES (id, nom) VALUES (?, ?)
                """,
                (matiere_id, matiere_name),
            )

        for matiere_id, colleur_id, jour_id, creneau_start, salle, groups in ROWS:
            cur.executemany(
                """
                INSERT INTO PLANNING (colleur_id, matiere_id, salle, jour_id, creneau_start, semaine, groupe)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        colleur_id,
                        matiere_id,
                        salle,
                        jour_id,
                        creneau_start,
                        semaine,
                        groupe,
                    )
                    for semaine, groupe in groups.items()
                ],
            )

        print(f"OK: {DB_PATH}")


if __name__ == "__main__":
    main()
