"""
SQL requests module
contains function to interract esaely with the database
"""

import sqlite3

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


def get_colle(groupe_id: int) -> Colle:
    """
    Fetch the DB and return a Colle class with the extracted data from the database
    """

    if not isinstance(cfg.CUR, sqlite3.Cursor):
        raise Exception("LALALALLA")

    _ = cfg.CUR.execute(
    """
        SELECT * FROM colleurs
        JOIN planning ON colleurs.id = planning.colleur_id
        WHERE planning.groupe = ?
    """,
    (groupe_id,)
    )

    rows = cfg.CUR.fetchone()

    colleur_name: str | None = rows["nom"]  # pyright: ignore[reportArgumentType, reportCallIssue]
    matiere: str | None = rows["matiere"] # pyright: ignore[reportArgumentType, reportCallIssue]
    jour: str | None = rows["jour"] # pyright: ignore[reportArgumentType, reportCallIssue]
    creneau: str | None = rows["creneau"] # pyright: ignore[reportArgumentType, reportCallIssue]
    salle: str | None = rows["salle"] # pyright: ignore[reportArgumentType, reportCallIssue]

    colle = Colle(
        colleur_name = colleur_name,  # pyright: ignore[reportArgumentType]
        matiere = matiere,  # pyright: ignore[reportArgumentType]
        jour = jour,  # pyright: ignore[reportArgumentType]
        creneau = creneau,  # pyright: ignore[reportArgumentType]
        salle = salle  # pyright: ignore[reportArgumentType]
    )
    return colle