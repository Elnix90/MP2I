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
from core.perms import is_bot_admin
from utils.console import _cmd_shutdown, get_console
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(name="restart", description="Redémarre le bot (réservé aux admins)")
    @app_commands.check(is_bot_admin)
    async def restart(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "restart", interaction)

        try:
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
                    "Error while restarting.",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Error while restarting.",
                    ephemeral=True,
                )
