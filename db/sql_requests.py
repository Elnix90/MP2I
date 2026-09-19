"""SQL requests module
contains function to interract esaely with the database
"""

import sqlite3
from datetime import datetime
from enum import Enum

from core.colle import Colle
from core.config import DB_PATH, cfg
from db.sql import load
from utils.logger import get_logger

logger = get_logger()

_COLLES_QUERY = load("colles")


class Jours(Enum):
    LUNDI = "Lundi"
    MARDI = "Mardi"
    MERCREDI = "Mercredi"
    JEUDI = "Jeudi"
    VENDREDI = "Vendredi"
    SAMEDI = "Samedi"
    DIMANCHE = "Dimanche"


JOURS = {index: jour.value for index, jour in enumerate(Jours)}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    logger.debug("[Get DB conn] Successfully connected")
    return conn


def get_colles(groupe_id: int) -> list[Colle]:
    cur = cfg.CUR
    if cur is None:
        logger.error("Failed to get colles: database cursor is not initialised")
        raise RuntimeError("Failed to get colles: database cursor is not initialised")

    dt = datetime.now()  # Fuck timezone we're french  # noqa: DTZ005
    week = int(dt.strftime("%W"))

    # Number of weeks since the planning start (14/09/2026). Before that
    # week, or after the planning horizon, there are no colles to report.
    magic_week = week - 36
    if magic_week < 1:
        logger.info("No colles before the planning start (week %d)", magic_week)
        return []

    cur.execute(
        _COLLES_QUERY,
        (groupe_id, magic_week),
    )

    rows = cur.fetchall()

    if rows is None:
        logger.error("Failed to get colles: db returned None")
        raise RuntimeError("Failed to get colles: db returned None")

    colles = []

    for row in rows:
        colles.append(
            Colle(
                colleur_name=row["colleur_name"],
                matiere=row["matiere"],
                jour=JOURS[row["jour_id"]],
                creneau=f"{row['creneau_start']}h-{row['creneau_start'] + 1}h",
                salle=row["salle"],
            ),
        )
    return colles
