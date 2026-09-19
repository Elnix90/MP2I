"""Shared helpers for memory-related commands."""

import discord

from managers.memory import make_scope_key


def interaction_scope(interaction: discord.Interaction) -> str:
    channel = interaction.channel
    if isinstance(channel, discord.Thread):
        return make_scope_key(thread_id=channel.id)
    return make_scope_key(channel_id=getattr(channel, "id", None))
