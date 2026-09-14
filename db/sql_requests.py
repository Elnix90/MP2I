"""
SQL requests module
contains function to interract esaely with the database
"""

import sqlite3
from datetime import datetime

from core.colle import Colle
from core.config import cfg
from utils.logger import get_logger

logger = get_logger()


def get_db_connection() -> sqlite3.Connection:
    """
    Connect to the SQLite database. If the DB file does not exist, create it.
    """

    conn = sqlite3.connect(cfg.DB_PATH)
    conn.row_factory = sqlite3.Row
    logger.debug("[Get DB conn] Successfully connected")
    return conn


def get_colles(groupe_id: int) -> list[Colle]:
    """
    Fetch the DB and return a Colle class with the extracted data from the database
    """

    if not isinstance(cfg.CUR, sqlite3.Cursor):
        raise Exception("LALALALLA")

    dt = datetime.now()  # Fuck timezone we're french
    week = int(dt.strftime("%W"))
    print(week)

    # That's the number of weeks of the year formatted to match a starting point the 14/09/2026
    magic_week = week - 36

    print(magic_week)

    _ = cfg.CUR.execute(
        """
        SELECT * FROM colleurs
        JOIN planning ON colleurs.id = planning.colleur_id
        WHERE planning.groupe = ?
        AND planning.semaine = ?
    """,
        (groupe_id, magic_week),
    )

    rows = cfg.CUR.fetchall()

    if rows is None:
        logger.error("Failed to get colles: db returned None")
        raise Exception("Failed to get colles: db returned None")

    colles = []

    for row in rows:
        colleur_name: str | None = row["nom"]  # pyright: ignore[reportArgumentType, reportCallIssue]
        matiere: str | None = row["matiere"]  # pyright: ignore[reportArgumentType, reportCallIssue]
        jour: str | None = row["jour"]  # pyright: ignore[reportArgumentType, reportCallIssue]
        creneau: str | None = row["creneau"]  # pyright: ignore[reportArgumentType, reportCallIssue]
        salle: str | None = row["salle"]  # pyright: ignore[reportArgumentType, reportCallIssue]

        colles.append(
            Colle(
                colleur_name=colleur_name,  # pyright: ignore[reportArgumentType]
                matiere=matiere,  # pyright: ignore[reportArgumentType]
                jour=jour,  # pyright: ignore[reportArgumentType]
                creneau=creneau,  # pyright: ignore[reportArgumentType]
                salle=salle,  #  pyright: ignore[reportArgumentType]
            )
        )
    return colles
