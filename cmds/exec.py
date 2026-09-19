"""Shell command handler.

Provides a `setup` function to register the `/exec_sh` command which runs
a shell command on the bot's host and returns its output.
"""

import time

import discord
from discord import app_commands

from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
    send_interaction,
)
from core.exec_shell_command import exec_shell_command
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()

MAX_OUTPUT_LEN = 1900


async def setup(tree: app_commands.CommandTree, bot):
    """Execs the given shell command in the server the bot is hosted in"""

    @tree.command(
        name="exec",
        description="Execute la commande SH donnée en argument sur le server ou le bot est host.",
    )
    @app_commands.check(is_bot_admin)
    async def exec(
        interaction: discord.Interaction,
        command: str,
        ephemeral: bool = True,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "exec", interaction)

        try:
            await defer_interaction(interaction)

            output = await exec_shell_command(command)
            if len(output) > MAX_OUTPUT_LEN:
                output = output[:MAX_OUTPUT_LEN] + "\n... (truncated)"

            await send_interaction(
                interaction,
                content=f"```\n{output}\n```",
                ephemeral=ephemeral,
            )

            log_command_end(logger, "exec", start_time)
        except Exception as exc:
            log_command_error(logger, "exec", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while executing the command.",
                )
            else:
                await interaction.followup.send("Error while executing the command.")
