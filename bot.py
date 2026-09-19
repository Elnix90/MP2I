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
from core.ai.channels import get_channel_mode
from core.ai.client import Answer, generate_answer, strip_tool_artifacts
from core.ai.prompts import build_system_prompt
from core.ai.tools import get_combined_tools
from core.config import cfg, perms_cfg
from core.perms import is_blacklisted_user_id
from db.settings_store import get_setting, set_setting
from managers.context import format_context_for_prompt, get_server_context
from managers.mcp import mcp_manager
from managers.memory import MemoryManager, make_scope_key
from utils.console import get_console
from utils.handlers.messages import MessageSender
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
        self._processing = set()
        self.bot_owners = set(perms_cfg.bot_admins)
        self.memory = MemoryManager(max_history=cfg.AI_MEMORY_MAX_HISTORY)
        with open(Path("config/statuses.json5")) as f:
            self.statuses = json5.load(f).get("statuses")

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        """Setup the game status task of the bot."""
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
        """Before starting the status changing task, we make sure the bot is ready."""
        await self.wait_until_ready()

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
        # Bootstrap memory and MCP concurrently to speed startup
        try:
            await asyncio.gather(self.memory.bootstrap(), mcp_manager.initialize())
        except Exception as exc:
            logger.error("Error during bootstrap/init: %s", exc)

        # load commands from cmds/ directory (loggers inside loader will report details)
        cmds_path = Path(__file__).parent / "cmds"
        await cmds_loader.load_commands(self, self.tree, cmds_path)
        await self._sync_commands_if_needed(cmds_path)
        self.status_task.start()

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
            or not cfg.AI_API_KEY
            or not cfg.AI_SYSTEM_PROMPT
            or not cfg.AI_API_URL
            or is_blacklisted_user_id(message.author.id)
            or self.user.mention not in message.content  # pyright: ignore[reportOptionalMemberAccess]
        ):
            return

        uid = message.author.id
        if uid in self._processing:
            return

        self._processing.add(uid)
        try:
            channel = message.channel

            if isinstance(channel, discord.Thread):
                parent_mode = get_channel_mode(channel.parent_id)
                if parent_mode == "thread":
                    await self._process(
                        message,
                        channel,
                        make_scope_key(thread_id=channel.id),
                    )
            else:
                mode = get_channel_mode(channel.id)
                if mode is None:
                    return
                if mode == "normal":
                    await self._process(
                        message,
                        channel,
                        make_scope_key(channel_id=channel.id),
                    )
                else:  # thread mode -> start a thread conversation
                    thread = await message.create_thread(
                        name=self._thread_name(message.content)
                    )
                    await self._process(
                        message,
                        thread,
                        make_scope_key(thread_id=thread.id),
                    )
        except Exception:
            logger.exception("Erreur lors du traitement du message IA")
            try:
                await message.channel.send("Une erreur interne m'empêche de répondre.")
            except Exception:
                pass
        finally:
            self._processing.discard(uid)

    @staticmethod
    def _flushable(buffer: str) -> bool:
        """True when the stream buffer ends at a safe block boundary.

        Prevents flushing in the middle of a code fence or a LaTeX fragment,
        which would break block detection and rendering.

        Parameters
        ----------
        buffer : str
            Pending streamed content.

        Returns
        -------
        bool
            True when the buffer can be sent as-is.
        """
        if buffer.count("```") % 2 != 0:
            return False
        for delimiter in ("$", r"\[", r"\]", r"\(", r"\)"):
            if buffer.count(delimiter) % 2 != 0:
                return False
        return True

    @staticmethod
    def _thread_name(content: str, max_length: int = 100) -> str:
        """Build a thread name from the message content."""
        topic = content.strip().replace("\n", " ")
        if len(topic) > max_length:
            topic = topic[:max_length].rstrip() + "…"
        return topic or "Conversation IA"

    @staticmethod
    def _strip_mention(content: str, bot_user: discord.ClientUser) -> str:
        """Remove the bot mention from the message content."""
        text = content
        text = text.replace(f"<@{bot_user.id}>", "").replace(f"<@!{bot_user.id}>", "")
        return text.strip()

    async def _process(
        self,
        message: discord.Message,
        channel: discord.abc.Messageable,
        scope: str,
    ) -> None:
        """Answer a mention in `channel`, using the memory scope `scope`."""
        user = message.author
        server_ctx = await get_server_context(message.guild)
        system_prompt = build_system_prompt(
            format_context_for_prompt(server_ctx),
            include_tools=True,
        )

        history = self.memory.get_history(scope)
        user_text = self._strip_mention(message.content, self.user)  # pyright: ignore[reportArgumentType]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append(
            {"role": "user", "content": f"[{user.display_name}]: {user_text}"}
        )

        full_content = ""
        sender = MessageSender(channel, self)
        async with channel.typing():
            result = await generate_answer(
                messages,
                stream=cfg.AI_STREAMING,
                tools=get_combined_tools(),
            )

            if isinstance(result, Answer):
                if result.error:
                    logger.warning(
                        "AI generation error=%s detail=%s",
                        result.error,
                        result.error_detail,
                    )
                full_content = strip_tool_artifacts(result.content or "")
            else:
                buffer = ""
                async for chunk in result:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content or ""
                    if not delta:
                        continue
                    full_content += delta
                    buffer += delta
                    if ("\n\n" in buffer or len(buffer) > 1500) and self._flushable(
                        buffer
                    ):
                        to_send = strip_tool_artifacts(buffer)
                        buffer = ""
                        if to_send.strip():
                            await sender.process_and_send(to_send)
                if buffer.strip():
                    await sender.process_and_send(strip_tool_artifacts(buffer))

        if isinstance(result, Answer):
            # non-stream path: send the complete answer now.
            await sender.process_and_send(full_content)

        if full_content.strip():
            thread = channel if isinstance(channel, discord.Thread) else None
            await self.memory.record_and_sync(
                user_id=user.id,
                user_name=user.display_name,
                user_content=user_text or message.content,
                assistant_content=strip_tool_artifacts(full_content),
                guild_id=message.guild.id if message.guild else None,
                channel_id=thread.parent_id if thread else channel.id,
                thread_id=thread.id if thread else None,
            )
        logger.info("Réponse envoyée à %s (scope=%s)", user.display_name, scope)


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
