import asyncio
import hashlib
import os
import random
import signal
import time
from pathlib import Path

import discord
import json5
from discord import app_commands
from discord.ext import tasks

from cmds import loader as cmds_loader
from core.ai.models import REFRESH_INTERVAL
from core.ai.models import refresh as refresh_models
from core.config import cfg, perms_cfg
from db.settings_store import get_setting, set_setting
from managers.ai_processor import AIProcessor
from managers.discord_search import init_discord_search
from managers.mcp import mcp_manager
from managers.memory import MemoryManager
from managers.notes import NoteManager
from utils.console import get_console
from utils.logger import get_logger

logger = get_logger()

FINGERPRINT_TTL = 7 * 24 * 3600

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class MP2IBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.bot_owners = set(perms_cfg.bot_admins)
        self.memory = MemoryManager(max_history=cfg.AI_MEMORY_MAX_HISTORY)
        self.notes = NoteManager()
        self.ai = AIProcessor(self, self.memory)
        with open(Path("config/statuses.json5")) as f:
            self.statuses = json5.load(f).get("statuses")

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        status = random.choice(self.statuses)
        if isinstance(status, dict):
            name = status["name"]
            if status.get("emoji"):
                name = f"{status['emoji']} {name}"
        else:
            name = status
        activity = discord.CustomActivity(name=name)
        await self.change_presence(activity=activity)

    @status_task.before_loop
    async def before_status_task(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(seconds=REFRESH_INTERVAL)
    async def models_task(self) -> None:
        """Keep the free+healthy model catalogue fresh: health changes without a restart."""
        await refresh_models(force=True)

    @models_task.before_loop
    async def before_models_task(self) -> None:
        await self.wait_until_ready()

    @staticmethod
    def _compute_commands_fingerprint(cmds_path: Path) -> str:
        hasher = hashlib.sha256()
        for py_file in sorted(cmds_path.glob("*.py")):
            if py_file.name.startswith("__"):
                continue
            st = py_file.stat()
            rel = py_file.name
            hasher.update(f"{rel}:{st.st_size}:{st.st_mtime_ns}".encode())
        return hasher.hexdigest()

    def _read_last_commands_fingerprint(self) -> str | None:
        fingerprint = get_setting("commands.fingerprint")
        updated_at = get_setting("commands.updatedAt")
        if not isinstance(fingerprint, str) or not isinstance(updated_at, int):
            return None
        if int(time.time()) - updated_at > FINGERPRINT_TTL:
            return None
        return fingerprint

    def _write_last_commands_fingerprint(self, fingerprint: str) -> None:
        set_setting("commands.fingerprint", fingerprint)
        set_setting("commands.updatedAt", int(time.time()))

    async def _sync_commands_if_needed(self, cmds_path: Path) -> None:
        force_sync = os.getenv("FORCE_COMMAND_SYNC", "0") == "1"
        skip_sync = os.getenv("SKIP_COMMAND_SYNC", "0") == "1"

        if skip_sync:
            logger.info("Skipping slash command sync (SKIP_COMMAND_SYNC=1)")
            return

        current_fingerprint = self._compute_commands_fingerprint(cmds_path)
        previous_fingerprint = self._read_last_commands_fingerprint()

        if not force_sync and previous_fingerprint == current_fingerprint:
            logger.info("Skipping slash command sync (no command changes detected)")
            return

        sync_start = time.perf_counter()
        await self.tree.sync()
        sync_elapsed = time.perf_counter() - sync_start
        self._write_last_commands_fingerprint(current_fingerprint)
        logger.info("Slash command sync completed in %.2fs", sync_elapsed)

    async def setup_hook(self):
        # Bootstrap memory, MCP and the model catalogue concurrently to speed startup
        try:
            await asyncio.gather(self.memory.bootstrap(), mcp_manager.initialize(), refresh_models())
        except Exception as exc:
            logger.error("Error during bootstrap/init: %s", exc)

        # Initialize Discord search client
        if cfg.AI_API_KEY:
            init_discord_search(cfg.AI_API_KEY)

        # load commands from cmds/ directory (loggers inside loader will report details)
        cmds_path = Path(__file__).parent / "cmds"
        await cmds_loader.load_commands(self, self.tree, cmds_path)
        await self._sync_commands_if_needed(cmds_path)
        self.status_task.start()
        self.models_task.start()

    async def on_ready(self):
        logger.info(
            "Bot MP2I est en ligne ! Connecté en tant que %s (ID: %s)",
            self.user,
            self.user.id,  # pyright: ignore[reportOptionalMemberAccess]
        )

    async def on_message(self, message):
        # DO NOT USE LOGGER HERE, otherwise the bot will send messages forever!
        try:
            await self.ai.handle_message(message)
        except Exception:
            logger.exception("Erreur lors du traitement du message IA")
            try:
                await message.channel.send("Une erreur interne m'empêche de répondre.")
            except Exception:
                pass


def run_bot():
    async def _main():
        client = MP2IBot(intents=intents)

        loop = asyncio.get_running_loop()

        def _on_signal():
            logger.info("Shutdown signal received, closing client...")
            # schedule close on the client; client.start will return after close
            loop.create_task(client.close())

        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(s, _on_signal)
            except NotImplementedError:
                # Windows or environments where add_signal_handler isn't supported
                pass

        get_console().attach(loop, client)

        try:
            await client.start(cfg.BOT_TOKEN)
        finally:
            try:
                if not client.is_closed():
                    await client.close()
            except Exception:
                logger.exception("Error closing client during shutdown")
            try:
                await client.memory.sync()
            except Exception:
                logger.exception("Error syncing memory during shutdown")
            await get_console().aclose()

    try:
        asyncio.run(_main())
    except Exception:
        logger.exception("Bot terminated with an exception")
