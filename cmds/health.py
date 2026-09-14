"""Health command handlers.

Provides a `setup` function to register the `/health` command which
performs runtime checks for subsystems and reports status.
"""

import discord
from discord import app_commands

from cmds._shared import (defer_interaction, log_command_error,
                          log_command_start)
from utils.logger import get_logger

logger = get_logger()


def _status_label(ok: bool) -> str:
    """Return a human-readable status label.

    Parameters
    ----------
    ok : bool
        True if the subsystem is healthy, False otherwise.

    Returns
    -------
    str
        "Healthy" when ok is True, otherwise "Degraded".
    """
    return "Healthy" if ok else "Degraded"


async def setup(tree: app_commands.CommandTree, bot):
    """Register the `health` command on the provided command tree.

    Parameters
    ----------
    tree : app_commands.CommandTree
        Command tree to register the command on.
    bot : Any
        Bot instance used to perform runtime checks.
    """

    @tree.command(name="health", description="Show runtime health for bot subsystems")
    async def health(interaction: discord.Interaction):
        """Perform runtime health checks and reply with a summary embed.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction that triggered the command.
        """
        log_command_start(logger, "health", interaction)

        await defer_interaction(interaction, ephemeral=True)
        logger.debug("Deferred interaction response")

        try:
            logger.debug("Starting health checks")
            gateway_ms = round(bot.latency * 1000, 2)

            # Discord readiness
            discord_ok = bot.is_ready()
            logger.debug(f"Discord readiness: {discord_ok}, latency: {gateway_ms}ms")

            await interaction.followup.send(
                content=f"Discord: {_status_label(discord_ok)} (latency: {gateway_ms}ms)",
                ephemeral=True,
            )

        except Exception as exc:
            log_command_error(logger, "health", exc)
            try:
                await interaction.followup.send(
                    "Error during health check.", ephemeral=True
                )
            except Exception as send_exc:
                logger.error(
                    "Failed to send error message: %s", send_exc, exc_info=True
                )
