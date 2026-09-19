"""Shared helpers for memory-related commands."""

import discord

from managers.memory import make_scope_key


def interaction_scope(interaction: discord.Interaction) -> str:
    """Resolve the memory scope of an interaction's channel.

    Threads get a per-thread scope; other channels share one scope.

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction invoking a command.

    Returns
    -------
    str
        Scope key for the current channel/thread.
    """
    channel = interaction.channel
    if isinstance(channel, discord.Thread):
        return make_scope_key(thread_id=channel.id)
    return make_scope_key(channel_id=getattr(channel, "id", None))
