import sqlite3
from pathlib import Path

from attr import dataclass
from discord.member import Member
from discord.user import User

from core.config import BASE_DIR
from db.sql import load

NOTES_DB_PATH = BASE_DIR / "data" / "notes.sqlite"

MAX_NOTE = 100

_SCHEMA = load("notes_shema")

_ADD_NOTE = load("add_note")
_REMOVE_NOTE = load("remove_note")
_LIST_NOTES = load("list_notes")

_ADD_NEW_DS = load("add_new_ds")
_DELETE_DS_NOTES = load("delete_ds_notes")
_DELETE_DS = load("delete_ds")
_GET_DS_BY_NAME = load("get_ds_by_name")
_LIST_DS = load("list_ds")


@dataclass
class Ds:
    id: int
    name: str

    def __str__(self) -> str:
        return f"« ***{self.name.strip()}*** »"


@dataclass
class Note:
    id: int
    user_id: int
    ds_id: int
    note: float


def _row_to_note(row: sqlite3.Row) -> Note:
    return Note(
        id=row["id"],
        user_id=row["user_id"],
        ds_id=row["ds"],
        note=row["note"],
    )


def _row_to_ds(row: sqlite3.Row) -> Ds:
    return Ds(id=row["id"], name=row["name"])


class NoteManager:
    def __init__(
        self,
        max_history: int = 15,
        *,
        db_path: Path | str = NOTES_DB_PATH,
    ) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        return self._conn

    def _init_db(self) -> None:
        self._get_conn()

    def add_note(self, user: User | Member, note: float, ds_id: int) -> bool:
        """Add a note to the current ds"""
        if not (0 <= note <= MAX_NOTE):
            raise ValueError(f"note must be between 0 and {MAX_NOTE}")
        conn = self._get_conn()
        row = conn.execute(_ADD_NOTE, (user.id, note, ds_id)).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("add_note returned no row id")
        return row[0]

    def remove_note(self, note_id: int) -> bool:
        conn = self._get_conn()
        cur = conn.execute(_REMOVE_NOTE, (note_id,))
        conn.commit()
        return cur.rowcount > 0

    def list_notes(self) -> list[Note]:
        conn = self._get_conn()
        rows = conn.execute(_LIST_NOTES).fetchall()
        return [_row_to_note(row) for row in rows]

    def add_new_ds(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("DS name cannot be empty")
        conn = self._get_conn()
        row = conn.execute(_ADD_NEW_DS, (name,)).fetchone()
        conn.commit()
        if row is None:
            raise RuntimeError("add_new_ds returned no row id")
        return row[0]

    def delete_ds(self, ds_id: int) -> int:
        """Supprime un DS et toutes ses notes, retourne le nombre de notes supprimées."""
        conn = self._get_conn()
        cur = conn.execute(_DELETE_DS_NOTES, (ds_id,))
        conn.execute(_DELETE_DS, (ds_id,))
        conn.commit()
        return max(cur.rowcount, 0)

    def get_ds_by_name(self, name: str) -> Ds | None:
        conn = self._get_conn()
        row = conn.execute(_GET_DS_BY_NAME, (name.strip(),)).fetchone()
        return _row_to_ds(row) if row is not None else None

    def list_ds(self) -> list[Ds]:
        conn = self._get_conn()
        rows = conn.execute(_LIST_DS).fetchall()
        return [_row_to_ds(row) for row in rows]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.commit()
            self._conn.close()
            self._conn = None
