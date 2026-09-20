"""Helpers to gather and format Discord server context.

Provides utilities to collect basic server metadata and format it for
inclusion in system prompts.
"""

import discord
from attr import dataclass
from discord.emoji import Emoji

from utils.logger import get_logger

logger = get_logger()


@dataclass
class ServerContext:
    server_name: str
    member_count: int
    server_emojis: tuple[Emoji, ...]

    def __str__(self) -> str:
        return (
            f"Information about the current Discord server '{self.server_name}':\n- Total member count: {self.member_count}\n- Server Emojis: {', '.join([str(emoji) for emoji in self.server_emojis])}"
        )


async def get_server_context(guild: discord.Guild) -> ServerContext:
    if not guild.chunked:
        try:
            await guild.chunk()
        except Exception:
            pass

    return ServerContext(server_name=guild.name, member_count=guild.member_count or 0, server_emojis=guild.emojis)
