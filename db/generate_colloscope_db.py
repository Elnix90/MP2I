"""Génère colloscope.db à partir du Colloscope MP2I S1 2026/2027.

Un créneau est étalé en un enregistrement PLANNING par (semaine, groupe).
Le schéma est normalisé : COLLEURS, MATIERES et PLANNING.
Les créneaux du bloc du haut (Ratte/Mensah/Gaudillat) sont des colles d'Anglais.
"""

from core.config import DB_PATH
from db.init.colleurs import COLLEURS
from db.init.rows import ROWS
from db.init.subjects import MATIERES
from db.sql import load
from db.sql_requests import get_db_connection

_SCHEMA = load("colloscope_schema")
_INSERT_COLLEUR = load("colleurs_insert")
_INSERT_MATIERE = load("matieres_insert")
_INSERT_PLANNING = load("planning_insert")


def main() -> None:
    if DB_PATH is None:
        return
    if DB_PATH.exists():
        DB_PATH.unlink()
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.executescript(_SCHEMA)

        for colleur_id, colleur_name in COLLEURS.items():
            cur.execute(_INSERT_COLLEUR, (colleur_id, colleur_name))

        for matiere_id, matiere_name in MATIERES.items():
            cur.execute(_INSERT_MATIERE, (matiere_id, matiere_name))

        for matiere_id, colleur_id, jour_id, creneau_start, salle, groups in ROWS:
            cur.executemany(
                _INSERT_PLANNING,
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
