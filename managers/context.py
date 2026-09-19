"""Helpers to gather and format Discord server context.

Provides utilities to collect basic server metadata and format it for
inclusion in system prompts.
"""

import discord

from utils.logger import get_logger

logger = get_logger()


async def get_server_context(guild: discord.Guild) -> dict:
    if not guild.chunked:
        try:
            await guild.chunk()
        except Exception:
            pass

    context = {"server_name": guild.name, "member_count": guild.member_count}
    return context
