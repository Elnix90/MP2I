"""Restart command handler.

Provides a `setup` function to register the `/restart` command. The bot
process is supervised and auto-restarts when it exits, so restarting
reuses the console's proven `shutdown` path: close the client, let the
process exit, and let the service manager bring it back up.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.is_admin import is_admin
from utils.console import _cmd_shutdown, get_console
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """Register the `restart` command on the given command tree.

    Parameters
    ----------
    tree : app_commands.CommandTree
        Command tree to register the command on.
    bot : Any
        Bot instance passed to command modules' setup functions.
    """

    @tree.command(name="restart", description="Redémarre le bot (réservé aux admins)")
    async def restart(interaction: discord.Interaction):
        """Acknowledge the request, then stop the bot so it restarts."""

        start_time = time.perf_counter()
        log_command_start(logger, "restart", interaction)

        try:
            if not is_admin(interaction.user):
                return await interaction.response.send_message(
                    "You don't have the permissions to use this command (cheh)",
                    ephemeral=True,
                )

            await interaction.response.send_message("Redémarrage du bot...")

            log_command_end(logger, "restart", start_time)

            # Same shutdown path as the console's `shutdown` command:
            # closing the client makes the process exit and the supervisor
            # restarts the bot.
            await _cmd_shutdown(get_console(), [])
        except Exception as exc:
            log_command_error(logger, "restart", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while restarting.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Error while restarting.", ephemeral=True
                )
