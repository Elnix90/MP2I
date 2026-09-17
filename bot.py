import asyncio
import hashlib
import json
import os
import signal
import time
from pathlib import Path

import discord
from discord import app_commands

from cmds import loader as cmds_loader
from core.ai import generate_answer, is_allowed_channel
from core.config import cfg
from utils.console import get_console
from utils.logger import get_logger

logger = get_logger()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


async def send_text_chunks(channel: discord.abc.Messageable, text: str, max_length: int = 2000) -> None:
    """Send `text` to `channel`, splitting it into Discord-sized chunks."""
    current = ""
    for line in text.splitlines():
        if len(line) > max_length:
            if current:
                await channel.send(current.rstrip())
                current = ""
            for i in range(0, len(line), max_length):
                await channel.send(line[i : i + max_length])
        elif len(current) + len(line) + 1 > max_length:
            await channel.send(current.rstrip())
            current = line
        else:
            current = f"{current}\n{line}"
    if current.strip():
        await channel.send(current.rstrip())


class MP2IBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self._processing = set()
        self._commands_sync_state_path = Path("data") / "command_sync_state.json"

    @staticmethod
    def _compute_commands_fingerprint(cmds_path: Path) -> str:
        """Fingerprint command sources to avoid unnecessary global sync at startup."""
        hasher = hashlib.sha256()
        for py_file in sorted(cmds_path.glob("*.py")):
            if py_file.name.startswith("__"):
                continue
            st = py_file.stat()
            rel = py_file.name
            hasher.update(f"{rel}:{st.st_size}:{st.st_mtime_ns}".encode())
        return hasher.hexdigest()

    def _read_last_commands_fingerprint(self) -> str | None:
        try:
            if not self._commands_sync_state_path.exists():
                return None
            with open(self._commands_sync_state_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return payload.get("fingerprint")
        except Exception:
            logger.warning("Failed to read command sync state", exc_info=True)
            return None

    def _write_last_commands_fingerprint(self, fingerprint: str) -> None:
        try:
            self._commands_sync_state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._commands_sync_state_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "fingerprint": fingerprint,
                        "updatedAt": int(time.time()),
                    },
                    f,
                    ensure_ascii=True,
                    indent=2,
                )
        except Exception:
            logger.warning("Failed to write command sync state", exc_info=True)

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
        # load commands from cmds/ directory (loggers inside loader will report details)
        cmds_path = Path(__file__).parent / "cmds"
        await cmds_loader.load_commands(self, self.tree, cmds_path)
        await self._sync_commands_if_needed(cmds_path)

    async def on_ready(self):
        logger.info(
            "Bot MP2I est en ligne ! Connecté en tant que %s (ID: %s)",
            self.user,
            self.user.id,  # pyright: ignore[reportOptionalMemberAccess]
        )

    async def on_message(self, message):

        # DO NOT USE LOGGER HERE, otherwise the bot will send messages forever!
        if (
            message.guild is None
            or message.guild.id != cfg.GUILD_ID
            or message.author.bot
            or not cfg.AI_ENABLED
            or not is_allowed_channel(message.channel.id)
            or not self.user.mention in message.content  # pyright: ignore[reportOptionalMemberAccess]
        ):
            return

        logger.info(f"Anwsering to {message.author.display_name}")

        uid = message.author.id
        if uid in self._processing:
            return

        self._processing.add(uid)
        try:
            async with message.channel.typing():
                messages = [
                    {"role": "system", "content": cfg.AI_SYSTEM_PROMPT},
                    {"role": "user", "content": message.content},
                ]
                answer = await generate_answer(messages)
                if answer:
                    await send_text_chunks(message.channel, answer)
        except Exception:
            logger.exception("Erreur lors du traitement du message IA")
            await message.channel.send("Une erreur interne m'empêche de répondre.")
        finally:
            self._processing.discard(uid)


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
            await get_console().aclose()

    try:
        asyncio.run(_main())
    except Exception:
        logger.exception("Bot terminated with an exception")
