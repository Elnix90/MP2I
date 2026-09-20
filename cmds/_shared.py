"""Shared helpers for command handlers.

Utility helpers for formatting interaction context and logging command
lifecycle events (start, end, error), plus helpers for deferring and
sending interaction responses.
"""

import time
from typing import Any

import discord


def interaction_context(interaction: Any) -> str:
    guild_name = interaction.guild.name if interaction.guild is not None else "DM"
    channel_name = getattr(interaction.channel, "name", None)
    channel_id = getattr(interaction.channel, "id", None)
    if channel_name is None:
        channel_name = f"#{channel_id}" if channel_id is not None else "unknown"

    return f"user={interaction.user} (id={interaction.user.id}), guild={guild_name}, channel={channel_name}"


def log_command_start(
    logger: Any,
    command_name: str,
    interaction: Any,
    **extra,
) -> None:
    details = interaction_context(interaction)
    if extra:
        details = f"{details}, extra={extra}"
    logger.info("Command /%s invoked (%s)", command_name, details)


def log_command_end(
    logger: Any,
    command_name: str,
    start_time: float,
    status: str = "ok",
) -> None:
    duration = time.perf_counter() - start_time
    logger.info("Command /%s completed in %.2fs (%s)", command_name, duration, status)


def _is_already_acknowledged(exc: Exception) -> bool:
    return isinstance(exc, discord.HTTPException) and getattr(exc, "code", None) == 40060


def log_command_error(logger: Any, command_name: str, exc: Exception) -> None:
    if _is_already_acknowledged(exc):
        logger.warning("Command /%s: interaction already acknowledged (40060)", command_name)
    else:
        logger.exception("Error in /%s: %s", command_name, exc)


async def defer_interaction(interaction: Any, *, ephemeral: bool = False) -> bool:
    if interaction.response.is_done():
        return False

    await interaction.response.defer(ephemeral=ephemeral)
    return True


async def send_interaction(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
    embed: Any = None,
    embeds: Any = None,
    ephemeral: bool = True,
) -> Any:
    kwargs = {}
    if content is not None:
        kwargs["content"] = content
    if embeds is not None:
        kwargs["embeds"] = embeds
    elif embed is not None:
        kwargs["embed"] = embed
    kwargs["ephemeral"] = ephemeral

    if interaction.response.is_done():
        return await interaction.followup.send(**kwargs)

    return await interaction.response.send_message(**kwargs)
