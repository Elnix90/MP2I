"""Memory management for conversation turns.

An in-memory manager for user-assistant conversation turns, scoped per
conversation container (channel for normal-mode channels, thread for
thread-mode channels), with per-user author tagging. Persistence is handled
by CocoIndex (SQLite), not by hand-rolled storage.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import cocoindex as coco
from cocoindex.connectors import sqlite as coco_sqlite

from core.config import BASE_DIR
from utils.logger import get_logger

logger = get_logger()

STATE_PATH = BASE_DIR / "data" / "memory_state.json"
SQLITE_PATH = BASE_DIR / "data" / "memory.sqlite"
COCOINDEX_DB_PATH = BASE_DIR / "data" / "cocoindex_memory.db"

MEMORY_STORE_KEY = coco.ContextKey["MemoryManager"]("mp2i_memory_store")
MEMORY_DB_KEY = coco.ContextKey[coco_sqlite.ManagedConnection]("mp2i_memory_db")

_ACTIVE_MEMORY_MANAGER: MemoryManager | None = None


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
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def scope_key(self) -> str:
        return make_scope_key(channel_id=self.channel_id, thread_id=self.thread_id)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@coco.lifespan
async def memory_lifespan(builder: coco.EnvironmentBuilder) -> AsyncIterator[None]:
    manager = _ACTIVE_MEMORY_MANAGER
    if manager is None:
        raise RuntimeError("MemoryManager is not initialized.")

    builder.settings.db_path = manager.cocoindex_db_path

    with coco_sqlite.managed_connection(manager.sqlite_path, load_vec=False) as conn:
        builder.provide(MEMORY_STORE_KEY, manager)
        builder.provide(MEMORY_DB_KEY, conn)
        yield


@coco.fn
async def memory_app_main() -> None:
    store = coco.use_context(MEMORY_STORE_KEY)

    # cocoindex's RowT TypeVar defaults to dict[str, Any], but dataclasses are
    # supported at runtime; cast to satisfy the stub.
    turn_schema = await coco_sqlite.TableSchema.from_class(
        cast("type[dict[str, Any]]", MemoryTurn),
        primary_key=["turn_id"],
    )
    turn_table = await coco_sqlite.mount_table_target(MEMORY_DB_KEY, "memory_turns", turn_schema)

    for turn in store.iter_turns():
        turn_table.declare_row(row=asdict(turn))


class MemoryManager:
    def __init__(
        self,
        max_history: int = 15,
        *,
        state_path: Path | str = STATE_PATH,
        sqlite_path: Path | str = SQLITE_PATH,
        cocoindex_db_path: Path | str = COCOINDEX_DB_PATH,
    ) -> None:
        global _ACTIVE_MEMORY_MANAGER

        _ACTIVE_MEMORY_MANAGER = self
        self.max_history = max_history
        self.state_path = Path(state_path)
        self.sqlite_path = Path(sqlite_path)
        self.cocoindex_db_path = Path(cocoindex_db_path)
        self._turns: dict[str, MemoryTurn] = {}
        self._sync_lock = asyncio.Lock()
        self._app = coco.App(coco.AppConfig(name="MP2IMemory"), memory_app_main)

        _ensure_parent_dir(self.state_path)
        _ensure_parent_dir(self.sqlite_path)
        _ensure_parent_dir(self.cocoindex_db_path)
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return

        for item in payload.get("turns", []) if isinstance(payload, dict) else []:
            try:
                turn = MemoryTurn(**item)
                self._turns[turn.turn_id] = turn
            except Exception as exc:
                logger.warning("Skipping invalid memory turn: %s", exc)

    def _save_state(self) -> None:
        payload = {"turns": [asdict(turn) for turn in self.iter_turns()]}
        tmp_path = self.state_path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
        tmp_path.replace(self.state_path)

    def iter_turns(self) -> Iterable[MemoryTurn]:
        return sorted(self._turns.values(), key=lambda t: (t.created_at, t.turn_id))

    def get_turn(self, turn_id: str) -> MemoryTurn:
        if turn_id in self._turns:
            return self._turns[turn_id]
        matches = [tid for tid in self._turns if tid.startswith(turn_id)]
        if not matches:
            raise KeyError(turn_id)
        if len(matches) > 1:
            raise ValueError(f"Turn ID '{turn_id}' is ambiguous.")
        return self._turns[matches[0]]

    def list_turns(self, scope_key: str | None = None, limit: int = 10) -> list[MemoryTurn]:
        turns = list(self.iter_turns())
        if scope_key is not None:
            turns = [t for t in turns if t.scope_key() == scope_key]
        return turns[-max(0, limit) :]

    def get_history(self, scope_key: str, limit: int | None = None) -> list[dict[str, str]]:
        limit = self.max_history if limit is None else limit
        turns = self.list_turns(scope_key, limit=limit)

        messages: list[dict[str, str]] = []
        for turn in turns:
            messages.append({"role": "user", "content": f"[{turn.user_name}]: {turn.user_content}"})
            if turn.assistant_content:
                messages.append({"role": "assistant", "content": turn.assistant_content})
        return messages

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
        self._turns[turn.turn_id] = turn
        return turn.turn_id

    def delete_turn(self, turn_id: str) -> MemoryTurn:
        resolved = self._resolve_turn_id(turn_id)
        return self._turns.pop(resolved)

    def _resolve_turn_id(self, turn_id: str) -> str:
        if turn_id in self._turns:
            return turn_id
        matches = [tid for tid in self._turns if tid.startswith(turn_id)]
        if not matches:
            raise KeyError(turn_id)
        if len(matches) > 1:
            raise ValueError(f"Turn ID '{turn_id}' is ambiguous.")
        return matches[0]

    def clear_history(self, scope_key: str | None = None) -> int:
        if scope_key is None:
            removed = len(self._turns)
            self._turns.clear()
            return removed

        removed_ids = [tid for tid, t in self._turns.items() if t.scope_key() == scope_key]
        for tid in removed_ids:
            self._turns.pop(tid, None)
        return len(removed_ids)

    async def sync(self) -> None:
        async with self._sync_lock:
            self._save_state()
            await self._app.update()

    async def bootstrap(self) -> None:
        await self.sync()

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
            )
            self._save_state()
            await self._app.update()
            return turn_id

    async def delete_turn_and_sync(self, turn_id: str) -> MemoryTurn:
        async with self._sync_lock:
            turn = self.delete_turn(turn_id)
            self._save_state()
            await self._app.update()
            return turn

    async def clear_history_and_sync(self, scope_key: str | None = None) -> int:
        async with self._sync_lock:
            removed = self.clear_history(scope_key)
            self._save_state()
            await self._app.update()
            return removed


active_memory: MemoryManager | None = None


def get_memory(max_history: int = 15) -> MemoryManager:
    global active_memory
    if active_memory is None:
        active_memory = MemoryManager(max_history=max_history)
    return active_memory
