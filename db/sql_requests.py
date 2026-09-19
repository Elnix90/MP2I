"""SQL requests module
contains function to interract esaely with the database
"""

import sqlite3
from datetime import datetime
from enum import Enum
from zoneinfo import ZoneInfo

from core.colle import Colle, ColleResult
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
    """Connect to the SQLite database. If the DB file does not exist, create it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    logger.debug("[Get DB conn] Successfully connected")
    return conn


def get_colles(groupe_id: int, week_id_requested: int | None) -> ColleResult | None:
    """Fetch the DB and return a Colle class with the extracted data from the database"""

    cur = cfg.CUR
    if cur is None:
        logger.error("Failed to get colles: database cursor is not initialised")
        raise RuntimeError("Failed to get colles: database cursor is not initialised")

    dt = datetime.now(ZoneInfo("Europe/Paris"))

    week = int(dt.strftime("%W"))
    # Number of weeks since the planning start (14/09/2026). Before that
    # week, or after the planning horizon, there are no colles to report.
    current_week = week - 36

    hour = int(dt.strftime("%H"))

    day_number_starting_from_sunday_who_the_fuck_decided_that_shit = int(dt.strftime("%w"))
    day_number = (day_number_starting_from_sunday_who_the_fuck_decided_that_shit + 6) % 7 + 1

    # When the day the user asks for colles is Friday or later in the week,
    # of that they specified the week_id they want the colles to be in
    # the bot returns the next week's colles
    if day_number >= 5 and week_id_requested is None:
        return get_colles(groupe_id, current_week + 1)

    if current_week < 1:
        logger.info("No colles before the planning start (week %d)", current_week)
        return

    cur.execute(
        _COLLES_QUERY,
        (groupe_id, week_id_requested or current_week),
    )

    rows: list[dict] = cur.fetchall()

    # If rows if empty
    if not rows:
        logger.error("Failed to get colles: db returned None")
        raise RuntimeError("Failed to get colles: db returned None")

    colles: list[Colle] = []

    for row in rows:
        colleur_name = row["colleur_name"]
        matiere = row["matiere"]
        jour: int = int(row["jour_id"])  # pyright: ignore[reportAssignmentType]
        crenau_start = int(row["creneau_start"])
        salle = row["salle"]

        print(f"current week: {current_week}, requested: {week_id_requested}, cond = {(week_id_requested is not None and current_week < week_id_requested)}")

        # User requested a week in the future
        # or the requested week is the current one, we are in the present week
        # or this colle's day is higher that the current one, the colle's happening in the future
        # or this colle is today and starts later
        is_future = (week_id_requested is not None and current_week < week_id_requested) or jour > day_number or (jour == day_number and crenau_start > hour)

        print(is_future)
        colles.append(
            Colle(colleur_name=colleur_name, matiere=matiere, jour=JOURS[jour], creneau=crenau_start, salle=salle, is_future=is_future),
        )

    return ColleResult(
        colles=colles,
        fetched_week=week_id_requested or current_week,
        current_week=current_week,
    )
