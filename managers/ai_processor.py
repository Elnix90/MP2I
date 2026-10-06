"""AI message processing pipeline.

Turns an incoming mention into a sent answer: gate checks, channel/thread
routing, prompt assembly, streamed generation and memory recording.
`bot.py` only delegates to :class:`AIProcessor`.
"""

import discord

from core.ai.channels import get_channel_mode
from core.ai.client import Answer, generate_answer, strip_tool_artifacts
from core.ai.prompts import build_system_prompt
from core.ai.tools import get_combined_tools
from core.config import cfg
from core.perms import is_blacklisted_user_id
from managers.context import get_server_context
from managers.memory import MemoryManager, make_scope_key
from managers.tools.discord_search import set_guild
from utils.debug import DebugWriter, new_turn_id
from utils.handlers.messages import MessageSender
from utils.logger import get_logger

logger = get_logger()

FLUSH_MIN_LENGTH = 1500
FLUSH_PARAGRAPH_LENGTH = 500


def strip_mention(content: str, bot_user: discord.ClientUser | None) -> str:
    """Remove the bot mention from `content` so it does not confuse the model."""
    if bot_user is None:
        return content.strip()
    text = content.replace(f"<@{bot_user.id}>", "").replace(f"<@!{bot_user.id}>", "")
    return text.strip()


def make_thread_name(content: str, max_length: int = 100) -> str:
    topic = content.strip().replace("\n", " ")
    if len(topic) > max_length:
        topic = topic[:max_length].rstrip() + "…"
    return topic or "Conversation IA"


def get_reply_url(message: discord.Message) -> str | None:
    """Jump URL of the message being replied to, if any."""
    reply_to = message.reference
    return reply_to.jump_url if reply_to else None


def is_flushable(buffer: str) -> bool:
    """True when `buffer` does not end inside a code block or math delimiter."""
    if buffer.count("```") % 2 != 0:
        return False
    for delimiter in ("$", r"\[", r"\]", r"\(", r"\)"):
        if buffer.count(delimiter) % 2 != 0:
            return False
    return True


def ends_inside_table(buffer: str) -> bool:
    tails = [line for line in buffer.splitlines() if line.strip()]
    return bool(tails and tails[-1].lstrip().startswith("|"))


class AIProcessor:
    """Routes mentions to the right conversation scope and generates answers."""

    def __init__(self, bot: discord.Client, memory: MemoryManager) -> None:
        self.bot = bot
        self.memory = memory
        self._processing: set[int] = set()

    async def handle_message(self, message: discord.Message) -> None:
        # DO NOT USE LOGGER BEFORE THE GATES, otherwise the bot will send messages forever!
        user = message.author
        guild = message.guild
        if (
            guild is None
            or guild.id != cfg.GUILD_ID
            or user.bot
            or not cfg.AI_ENABLED
            or not cfg.AI_API_KEY
            or not cfg.AI_SYSTEM_PROMPT
            or not cfg.AI_API_URL
            or is_blacklisted_user_id(user.id)
            or self.bot.user is None
            or self.bot.user.mention not in message.content
        ):
            return

        logger.info("Answering to %s", user.display_name)

        uid = user.id
        if uid in self._processing:
            return

        self._processing.add(uid)
        try:
            channel = message.channel

            if isinstance(channel, discord.Thread):
                parent_mode = get_channel_mode(channel.parent_id)
                if parent_mode == "thread":
                    await self.process(message, channel, make_scope_key(thread_id=channel.id))
                return

            channel_id = getattr(channel, "id", None)
            mode = get_channel_mode(channel_id)
            if mode is None:
                return
            if mode == "normal":
                await self.process(message, channel, make_scope_key(channel_id=channel_id))
            else:  # thread mode -> start a thread conversation
                thread = await message.create_thread(name=make_thread_name(message.content))
                await self.process(message, thread, make_scope_key(thread_id=thread.id))
        finally:
            self._processing.discard(uid)

    async def process(
        self,
        message: discord.Message,
        channel: discord.abc.Messageable,
        scope: str,
    ) -> None:
        if message.guild is None:
            return
        user = message.author
        # Set guild for discord_search tool
        set_guild(message.guild)

        server_ctx = await get_server_context(message.guild, replying_to=get_reply_url(message))
        system_prompt = build_system_prompt(
            server_context=str(server_ctx),
            include_tools=True,
        )

        user_text = strip_mention(message.content, self.bot.user)

        history = await self.memory.get_context(
            scope,
            user_id=user.id,
            current_query=user_text or message.content,
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": f"[{user.display_name}]: {user_text}"})

        full_content = ""
        turn_id = new_turn_id()
        debug: DebugWriter | None = DebugWriter(turn_id, channel, user) if cfg.DEBUG_MODE else None
        sender = MessageSender(channel, self.bot, debug=debug)
        async with channel.typing():
            tools = get_combined_tools()

            result = await generate_answer(
                messages,
                stream=cfg.AI_STREAMING,
                tools=tools,
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
                    if (len(buffer) > FLUSH_MIN_LENGTH or ("\n\n" in buffer and len(buffer) > FLUSH_PARAGRAPH_LENGTH)) and is_flushable(buffer) and not ends_inside_table(buffer):
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
                channel_id=thread.parent_id if thread else getattr(channel, "id", None),
                thread_id=thread.id if thread else None,
                turn_id=turn_id,
            )
        if debug:
            debug.save(user_text or message.content)
        logger.info("Réponse envoyée à %s (scope=%s)", user.display_name, scope)
