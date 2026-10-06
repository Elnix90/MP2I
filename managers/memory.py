"""Memory management for conversation turns.

SQLite-backed memory with semantic search via sqlite-vec and local embeddings
(``utils/embedder``). Provides both legacy get_history() (last N turns) and
intelligent get_context() that selects relevant past turns based on the
current query.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import struct
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import sqlite_vec
from openai import AsyncOpenAI

from core.config import BASE_DIR, cfg
from db.sql import load
from utils import embedder
from utils.logger import get_logger

logger = get_logger()

MEMORY_DB_PATH = BASE_DIR / "data" / "memory.sqlite"
EMBEDDING_DIM = embedder.DIM

_AI_CLIENT: AsyncOpenAI | None = None


def _ai_client() -> AsyncOpenAI:
    global _AI_CLIENT
    if _AI_CLIENT is None:
        _AI_CLIENT = AsyncOpenAI(base_url=cfg.AI_API_URL, api_key=cfg.AI_API_KEY, timeout=30.0)
    return _AI_CLIENT


def _models_priority() -> list[str]:
    """Model rotation for fact extraction: same order as the chat client."""
    from core.ai import models as model_catalog

    return model_catalog.priority()


_FACTS_SYSTEM = (
    "Tu extrais des faits factuels sur un utilisateur à partir d'une conversation. "
    'Réponds uniquement en JSON : {"facts": [string, ...]}. '
    "N'extrais que des phrases complètes et durables (au moins 10 caractères, contenant un espace). "
    "Ignore les expressions mathématiques, les mots isolés et les pensées incomplètes. "
    '0 à 2 faits maximum. Rien d\'exploitable ? renvoie {"facts": []}.'
)


def _parse_facts_json(content: str) -> list[str]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("facts"), list):
        return [str(f).strip() for f in data["facts"]]
    if isinstance(data, list):
        return [str(f).strip() for f in data]
    return []


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
            # Recreate the virtual table if its embedding dimension is stale.
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='vec_turns'").fetchone()
            if row is not None and f"float[{EMBEDDING_DIM}]" not in (row[0] or ""):
                logger.warning("vec_turns dimension mismatch, recreating table (embedding dim %d)", EMBEDDING_DIM)
                conn.execute("DROP TABLE vec_turns")
            conn.execute(_CREATE_VEC_TABLE.format(dim=EMBEDDING_DIM))
            logger.info("sqlite-vec loaded, vec_turns table ready")
        except Exception as exc:
            logger.warning("Failed to load sqlite-vec, semantic search disabled: %s", exc)

    async def _embed(self, text: str) -> list[float] | None:
        try:
            embedding = await embedder.aembed(text)
            if len(embedding) != EMBEDDING_DIM:
                logger.warning("Embedding dim mismatch: got %d, expected %d", len(embedding), EMBEDDING_DIM)
                return None
            return embedding
        except Exception as exc:
            logger.warning("Embedding failed: %s", exc)
            return None

    async def _extract_facts(self, user_name: str, user_content: str, assistant_content: str) -> list[str]:
        prompt = f"User ({user_name}): {user_content}\nAssistant: {assistant_content}\n"
        for model in _models_priority():
            try:
                resp = await _ai_client().chat.completions.create(
                    model=model,
                    max_tokens=128,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": _FACTS_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                content = resp.choices[0].message.content or ""
                facts = [f for f in _parse_facts_json(content) if len(f) >= 10 and " " in f][:3]
                if facts:
                    return facts
            except Exception as exc:
                logger.debug("Fact extraction failed on %s: %s", model, exc)
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
        conn.commit()
        return turn.turn_id

    async def _enrich_turn(
        self,
        *,
        turn_id: str,
        rowid: int | None,
        combined: str,
        user_id: int,
        user_name: str,
        user_content: str,
        assistant_content: str,
    ) -> None:
        """Embed the turn and extract user facts, both over the network, off the hot path."""
        embedding = await self._embed(combined)
        if embedding is not None and rowid is not None:
            async with self._sync_lock:
                try:
                    self._upsert_vector(self._get_conn(), rowid, embedding)
                    self._get_conn().commit()
                except Exception as exc:
                    logger.debug("Failed to store embedding for turn %s: %s", turn_id[:8], exc)

        facts = await self._extract_facts(user_name, user_content, assistant_content)
        if facts:
            async with self._sync_lock:
                for fact in facts[:3]:
                    self.add_user_fact(user_id, fact, source_turn_ids=[turn_id])

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

    async def get_context(
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
            embedding = await self._embed(current_query)
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
        try:
            await asyncio.to_thread(embedder.warmup)
        except Exception as exc:
            logger.warning("Embedding model warmup failed: %s", exc)
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
            embedding = await self._embed(combined)
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
            turn_id = self.record_exchange(
                user_id=user_id,
                user_name=user_name,
                user_content=user_content,
                assistant_content=assistant_content,
                guild_id=guild_id,
                channel_id=channel_id,
                thread_id=thread_id,
                turn_id=turn_id,
            )
            row = self._get_conn().execute(_GET_ROWID, (turn_id,)).fetchone()
            rowid = row[0] if row is not None else None
        combined = f"{user_name}: {user_content}"
        if assistant_content:
            combined += f"\n{assistant_content}"
        asyncio.create_task(
            self._enrich_turn(
                turn_id=turn_id,
                rowid=rowid,
                combined=combined,
                user_id=user_id,
                user_name=user_name,
                user_content=user_content,
                assistant_content=assistant_content,
            )
        )
        return turn_id

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
