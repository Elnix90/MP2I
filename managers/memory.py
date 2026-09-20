"""Memory management for conversation turns.

SQLite-backed memory with semantic search via sqlite-vec and needle embeddings.
Provides both legacy get_history() (last N turns) and intelligent get_context()
that selects relevant past turns based on the current query.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import struct
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import sqlite_vec

from core.config import BASE_DIR
from db.sql import load
from utils.logger import get_logger

logger = get_logger()

MEMORY_DB_PATH = BASE_DIR / "data" / "memory.sqlite"
EMBEDDING_DIM = 3072  # needle v3 embedding dimension

# SQL queries
_SCHEMA = load("memory_schema")
_UPSERT_TURN = load("memory_upsert")
_LIST_BY_SCOPE = load("memory_list_by_scope")
_GET_TURN = load("memory_get_turn")
_DELETE_TURN = load("memory_delete_turn")
_CLEAR_SCOPE = load("memory_clear_scope")
_UPSERT_USER_FACT = load("memory_upsert_user_fact")
_GET_USER_FACTS = load("memory_get_user_facts")
_CLEAR_USER_FACTS = load("memory_clear_user_facts")
_UPSERT_CHANNEL_FACT = load("memory_upsert_channel_fact")
_GET_CHANNEL_FACTS = load("memory_get_channel_facts")
_CLEAR_CHANNEL_FACTS = load("memory_clear_channel_facts")
_PRAGMA_BUSY = load("memory_pragma_busy")
_PRAGMA_WAL = load("memory_pragma_wal")
_TABLE_INFO = load("memory_table_info")
_ALTER_ADD_SCOPE_KEY = load("memory_alter_add_scope_key")
_BACKFILL_SCOPE_KEY = load("memory_backfill_scope_key")
_CREATE_VEC_TABLE = load("memory_create_vec_table")
_VEC_DELETE = load("memory_vec_delete")
_VEC_INSERT = load("memory_vec_insert")
_VEC_SEARCH_ALL = load("memory_vec_search_all")
_VEC_SEARCH_SCOPE = load("memory_vec_search_scope")
_GET_ROWID = load("memory_get_rowid")
_GET_TURN_BY_PREFIX = load("memory_get_turn_by_prefix")
_LIST_RECENT_ALL = load("memory_list_recent_all")
_ITERATE_ALL = load("memory_iterate_all")
_COUNT_ALL = load("memory_count_all")
_DELETE_ALL = load("memory_delete_all")
_COUNT_SCOPE = load("memory_count_scope")
_COUNT_USER_FACT = load("memory_count_user_fact")
_FTS_SEARCH_SCOPE = load("memory_fts_search_scope")
_FTS_SEARCH_ALL = load("memory_fts_search_all")
_BACKFILL_SELECT = load("memory_backfill_select")


def make_scope_key(*, channel_id: int | None = None, thread_id: int | None = None) -> str:
    if thread_id is not None:
        return f"thread:{thread_id}"
    return f"channel:{channel_id}"


@dataclass(slots=True)
class MemoryTurn:
    turn_id: str
    user_id: int
    user_name: str
    guild_id: int | None
    channel_id: int | None
    user_content: str
    assistant_content: str | None = None
    thread_id: int | None = None
    scope_key: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.scope_key:
            self.scope_key = make_scope_key(channel_id=self.channel_id, thread_id=self.thread_id)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _row_to_turn(row: sqlite3.Row) -> MemoryTurn:
    return MemoryTurn(
        turn_id=row["turn_id"],
        user_id=row["user_id"],
        user_name=row["user_name"],
        guild_id=row["guild_id"],
        channel_id=row["channel_id"],
        thread_id=row["thread_id"],
        user_content=row["user_content"],
        assistant_content=row["assistant_content"],
        scope_key=row["scope_key"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _fact_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "fact_id": row["fact_id"],
        "fact": row["fact"],
        "source_turn_ids": json.loads(row["source_turn_ids"]) if row["source_turn_ids"] else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class MemoryManager:
    def __init__(
        self,
        max_history: int = 15,
        *,
        db_path: Path | str = MEMORY_DB_PATH,
    ) -> None:
        self.max_history = max_history
        self.db_path = Path(db_path)
        self._sync_lock = asyncio.Lock()
        self._needle_agent = None
        self._conn: sqlite3.Connection | None = None

        _ensure_parent_dir(self.db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(_PRAGMA_BUSY)
            self._conn.execute(_PRAGMA_WAL)
            self._migrate_schema(self._conn)
            self._conn.executescript(_SCHEMA)
            self._init_vec_table()
            self._conn.commit()
        return self._conn

    def _init_db(self) -> None:
        self._get_conn()

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Migrate old schema to new: add scope_key column if missing."""
        try:
            columns = {row[1] for row in conn.execute(_TABLE_INFO).fetchall()}
            if "scope_key" not in columns:
                logger.info("Migrating memory_turns: adding scope_key column")
                conn.execute(_ALTER_ADD_SCOPE_KEY)
                # Backfill scope_key from existing channel_id/thread_id
                conn.execute(_BACKFILL_SCOPE_KEY)
        except Exception as exc:
            logger.warning("Schema migration failed (may be fresh DB): %s", exc)

    def _init_vec_table(self) -> None:
        conn = self._conn
        if conn is None:
            return
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            conn.execute(_CREATE_VEC_TABLE.format(dim=EMBEDDING_DIM))
            logger.info("sqlite-vec loaded, vec_turns table ready")
        except Exception as exc:
            logger.warning("Failed to load sqlite-vec, semantic search disabled: %s", exc)

    def _get_needle(self):
        if self._needle_agent is None:
            try:
                import needle

                self._needle_agent = needle.Needle(tools=[], generation=3)
            except Exception as exc:
                logger.warning("Failed to load needle for embeddings: %s", exc)
                return None
        return self._needle_agent

    def _embed(self, text: str) -> list[float] | None:
        agent = self._get_needle()
        if agent is None:
            return None
        try:
            return agent.embed(text)
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    def _extract_facts(self, user_name: str, user_content: str, assistant_content: str) -> list[str]:
        agent = self._get_needle()
        if agent is None:
            return []
        try:
            from pydantic import BaseModel

            class ExtractedFacts(BaseModel):
                facts: list[str]

            prompt = (
                f"Extract factual information about the user from this conversation. "
                f"Only extract complete, meaningful sentences. Ignore math expressions, "
                f"single words, or incomplete thoughts.\n\n"
                f"User ({user_name}): {user_content}\n"
                f"Assistant: {assistant_content}\n\n"
                "Return 0-2 facts. Examples of good facts:\n"
                "- Alice is a student in MP2I prep class\n"
                "- Bob prefers using Python for programming\n"
                "- Charlie asked about derivatives of polynomials\n\n"
                "If nothing meaningful can be extracted, return an empty list."
            )
            result = agent.extract(prompt, ExtractedFacts)
            if isinstance(result, ExtractedFacts):
                facts = result.facts
            elif isinstance(result, dict) and "facts" in result:
                facts = result["facts"]
            else:
                return []
            # Filter: keep only facts that are complete sentences (min 10 chars, contain spaces)
            return [f for f in facts if len(f) >= 10 and " " in f]
        except Exception as exc:
            logger.debug("Fact extraction failed: %s", exc)
            return []

    def _embedding_to_bytes(self, vec: list[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    def _upsert_vector(self, conn: sqlite3.Connection, rowid: int, embedding: list[float]) -> None:
        conn.execute(_VEC_DELETE, (rowid,))
        conn.execute(_VEC_INSERT, (rowid, self._embedding_to_bytes(embedding)))

    def _bytes_to_embedding(self, data: bytes) -> list[float]:
        return list(struct.unpack(f"{len(data) // 4}f", data))

    # --- Core CRUD (SQLite-backed) ---

    def record_exchange(
        self,
        *,
        user_id: int,
        user_name: str,
        user_content: str,
        assistant_content: str,
        guild_id: int | None,
        channel_id: int | None,
        thread_id: int | None = None,
        turn_id: str | None = None,
    ) -> str:
        turn = MemoryTurn(
            turn_id=turn_id or uuid.uuid4().hex,
            user_id=user_id,
            user_name=user_name,
            guild_id=guild_id,
            channel_id=channel_id,
            thread_id=thread_id,
            user_content=user_content,
            assistant_content=assistant_content,
        )
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            _UPSERT_TURN,
            (
                turn.turn_id,
                turn.user_id,
                turn.user_name,
                turn.guild_id,
                turn.channel_id,
                turn.thread_id,
                turn.user_content,
                turn.assistant_content,
                turn.scope_key,
                now,
                now,
            ),
        )
        # Store embedding for the combined text
        combined = f"{user_name}: {user_content}"
        if turn.assistant_content:
            combined += f"\n{turn.assistant_content}"
        embedding = self._embed(combined)
        if embedding is not None:
            # Get the auto-assigned rowid from the INSERT above
            rowid = conn.execute(
                _GET_ROWID,
                (turn.turn_id,),
            ).fetchone()
            if rowid is not None:
                try:
                    self._upsert_vector(conn, rowid[0], embedding)
                except Exception as exc:
                    logger.debug("Failed to store embedding for turn %s: %s", turn.turn_id[:8], exc)

        # Extract and store user facts asynchronously (fire-and-forget)
        try:
            facts = self._extract_facts(user_name, user_content, assistant_content or "")
            for fact in facts[:3]:  # limit to 3 facts per exchange
                self.add_user_fact(user_id, fact, source_turn_ids=[turn.turn_id])
        except Exception as exc:
            logger.debug("Fact extraction skipped: %s", exc)

        return turn.turn_id

    def get_turn(self, turn_id: str) -> MemoryTurn:
        conn = self._get_conn()
        # Try exact match first
        row = conn.execute(_GET_TURN, (turn_id,)).fetchone()
        if row is not None:
            return _row_to_turn(row)
        # Try prefix match
        rows = conn.execute(
            _GET_TURN_BY_PREFIX,
            (f"{turn_id}%",),
        ).fetchall()
        if not rows:
            raise KeyError(turn_id)
        if len(rows) > 1:
            raise ValueError(f"Turn ID '{turn_id}' is ambiguous.")
        full_id = rows[0]["turn_id"]
        row = conn.execute(_GET_TURN, (full_id,)).fetchone()
        return _row_to_turn(row)

    def list_turns(self, scope_key: str | None = None, limit: int = 10) -> list[MemoryTurn]:
        conn = self._get_conn()
        if scope_key is not None:
            rows = conn.execute(_LIST_BY_SCOPE, (scope_key, limit)).fetchall()
        else:
            rows = conn.execute(_LIST_RECENT_ALL, (limit,)).fetchall()
        return [_row_to_turn(r) for r in reversed(rows)]

    def delete_turn(self, turn_id: str) -> MemoryTurn:
        turn = self.get_turn(turn_id)
        conn = self._get_conn()
        conn.execute(_DELETE_TURN, (turn.turn_id,))
        conn.commit()
        return turn

    def clear_history(self, scope_key: str | None = None) -> int:
        conn = self._get_conn()
        if scope_key is None:
            count = conn.execute(_COUNT_ALL).fetchone()[0]
            conn.execute(_DELETE_ALL)
            conn.commit()
            return count
        count = conn.execute(
            _COUNT_SCOPE,
            (scope_key,),
        ).fetchone()[0]
        conn.execute(_CLEAR_SCOPE, (scope_key,))
        conn.commit()
        return count

    # --- History (legacy API, backward compat) ---

    def iter_turns(self) -> Iterable[MemoryTurn]:
        conn = self._get_conn()
        rows = conn.execute(_ITERATE_ALL).fetchall()
        return [_row_to_turn(r) for r in rows]

    def get_history(self, scope_key: str, limit: int | None = None) -> list[dict[str, str]]:
        limit = self.max_history if limit is None else limit
        turns = self.list_turns(scope_key, limit=limit)
        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": f"[{turn.user_name}]: {turn.user_content}"})
            if turn.assistant_content:
                messages.append({"role": "assistant", "content": turn.assistant_content})
        return messages

    # --- Semantic search (new) ---

    def _search_vec(
        self,
        query_embedding: list[float],
        scope_key: str | None = None,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        conn = self._get_conn()
        query_bytes = self._embedding_to_bytes(query_embedding)
        try:
            if scope_key:
                rows = conn.execute(
                    _VEC_SEARCH_SCOPE,
                    (query_bytes, top_k, scope_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    _VEC_SEARCH_ALL,
                    (query_bytes, top_k),
                ).fetchall()
            return [(r["turn_id"], r["distance"]) for r in rows]
        except Exception as exc:
            logger.warning("Vector search failed: %s", exc)
            return []

    def _fts_search(
        self,
        query: str,
        scope_key: str | None = None,
        limit: int = 10,
    ) -> list[str]:
        conn = self._get_conn()
        try:
            if scope_key:
                rows = conn.execute(
                    _FTS_SEARCH_SCOPE,
                    (scope_key, f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    _FTS_SEARCH_ALL,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            return [r["turn_id"] for r in rows]
        except Exception as exc:
            logger.warning("FTS search failed: %s", exc)
            return []

    def get_context(
        self,
        scope_key: str,
        user_id: int | None = None,
        current_query: str = "",
        max_tokens: int = 4000,
    ) -> list[dict[str, str]]:
        """Intelligent context selection: semantic search + session memory + user facts.

        Returns messages in optimal order for the LLM:
        1. User facts (if user_id provided)
        2. Semantically relevant past turns
        3. Last N session turns
        """
        messages: list[dict[str, str]] = []
        used_turn_ids: set[str] = set()

        # 1. User facts (cross-session context)
        if user_id is not None:
            facts = self.get_user_facts(user_id, limit=10)
            if facts:
                facts_text = "\n".join(f"- {f['fact']}" for f in facts)
                messages.append(
                    {
                        "role": "system",
                        "content": f"Ce que tu sais sur cet utilisateur:\n{facts_text}",
                    }
                )

        # 2. Semantic search for relevant past turns
        if current_query.strip():
            embedding = self._embed(current_query)
            if embedding is not None:
                semantic_hits = self._search_vec(embedding, scope_key=scope_key, top_k=10)
                for turn_id, distance in semantic_hits[:5]:
                    turn = self.get_turn(turn_id)
                    if turn.turn_id not in used_turn_ids:
                        messages.append(
                            {
                                "role": "user",
                                "content": f"[{turn.user_name}]: {turn.user_content}",
                            }
                        )
                        if turn.assistant_content:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": turn.assistant_content,
                                }
                            )
                        used_turn_ids.add(turn.turn_id)

            # Fallback: keyword search if not enough semantic results
            if len(messages) < 3:
                fts_hits = self._fts_search(current_query, scope_key=scope_key, limit=5)
                for turn_id in fts_hits:
                    if turn_id not in used_turn_ids:
                        turn = self.get_turn(turn_id)
                        messages.append(
                            {
                                "role": "user",
                                "content": f"[{turn.user_name}]: {turn.user_content}",
                            }
                        )
                        if turn.assistant_content:
                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": turn.assistant_content,
                                }
                            )
                        used_turn_ids.add(turn.turn_id)

        # 3. Last N session turns (most recent context)
        session_turns = self.list_turns(scope_key, limit=self.max_history)
        for turn in reversed(session_turns):
            if turn.turn_id not in used_turn_ids:
                messages.append(
                    {
                        "role": "user",
                        "content": f"[{turn.user_name}]: {turn.user_content}",
                    }
                )
                if turn.assistant_content:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": turn.assistant_content,
                        }
                    )
                used_turn_ids.add(turn.turn_id)

        # Budget truncation: keep system messages + most recent if over limit
        if len(messages) > max_tokens // 100:  # rough estimate
            messages = messages[-(max_tokens // 100) :]

        return messages

    # --- User facts ---

    def get_user_facts(self, user_id: int, limit: int = 10) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(_GET_USER_FACTS, (user_id, limit)).fetchall()
        return [_fact_row_to_dict(r) for r in rows]

    def add_user_fact(
        self,
        user_id: int,
        fact: str,
        source_turn_ids: list[str] | None = None,
    ) -> str:
        fact_id = uuid.uuid4().hex
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            _UPSERT_USER_FACT,
            (
                fact_id,
                user_id,
                fact,
                json.dumps(source_turn_ids or []),
                now,
                now,
            ),
        )
        conn.commit()
        return fact_id

    def clear_user_facts(self, user_id: int) -> int:
        conn = self._get_conn()
        count = conn.execute(
            _COUNT_USER_FACT,
            (user_id,),
        ).fetchone()[0]
        conn.execute(_CLEAR_USER_FACTS, (user_id,))
        conn.commit()
        return count

    # --- Sync (no-op for SQLite, kept for backward compat) ---

    async def sync(self) -> None:
        conn = self._get_conn()
        conn.commit()

    async def bootstrap(self) -> None:
        self._get_conn()
        await self._backfill_embeddings()

    async def _backfill_embeddings(self) -> None:
        """Generate embeddings for existing turns that don't have one yet."""
        conn = self._get_conn()
        rows = conn.execute(_BACKFILL_SELECT).fetchall()
        if not rows:
            return
        logger.info("Backfilling embeddings for %d existing turns", len(rows))
        for row in rows:
            combined = f"{row['user_name']}: {row['user_content']}"
            if row["assistant_content"]:
                combined += f"\n{row['assistant_content']}"
            embedding = self._embed(combined)
            if embedding is not None:
                try:
                    self._upsert_vector(conn, row["rowid"], embedding)
                except Exception as exc:
                    logger.debug("Backfill failed for %s: %s", row["turn_id"][:8], exc)
        conn.commit()
        logger.info("Backfill complete: %d turns embedded", len(rows))

    async def record_and_sync(
        self,
        *,
        user_id: int,
        user_name: str,
        user_content: str,
        assistant_content: str,
        guild_id: int | None,
        channel_id: int | None,
        thread_id: int | None = None,
        turn_id: str | None = None,
    ) -> str:
        async with self._sync_lock:
            return self.record_exchange(
                user_id=user_id,
                user_name=user_name,
                user_content=user_content,
                assistant_content=assistant_content,
                guild_id=guild_id,
                channel_id=channel_id,
                thread_id=thread_id,
                turn_id=turn_id,
            )

    async def delete_turn_and_sync(self, turn_id: str) -> MemoryTurn:
        async with self._sync_lock:
            return self.delete_turn(turn_id)

    async def clear_history_and_sync(self, scope_key: str | None = None) -> int:
        async with self._sync_lock:
            return self.clear_history(scope_key)


active_memory: MemoryManager | None = None


def get_memory(max_history: int = 15) -> MemoryManager:
    global active_memory
    if active_memory is None:
        active_memory = MemoryManager(max_history=max_history)
    return active_memory
