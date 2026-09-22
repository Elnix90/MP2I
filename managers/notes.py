import sqlite3
from pathlib import Path

from core.config import BASE_DIR
from db.sql import load

NOTES_DB_PATH = BASE_DIR / "data" / "notes.sqlite"


_SCHEMA = load("notes_shema")


class NotsManager:
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
