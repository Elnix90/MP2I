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
from core.is_admin import is_admin
from utils.logger import get_logger

logger = get_logger()

MAX_OUTPUT_LEN = 1900


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="self-update",
        description="Automatiquement met à jour le bot depuis son serveur distant",
    )
    async def self_update(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "self_update", interaction)

        try:
            if not is_admin(interaction.user):
                return await interaction.response.send_message(
                    "You don't have the permissions to use this command (cheh)",
                    ephemeral=True,
                )

            await defer_interaction(interaction)

            update_cmd = """
                git remote | while read remote; do git remote remove $remote; done
                git remote add origin https://github.com/Elnix90/MP2I.git
                git fetch origin
                git checkout prod
                git reset --hard origin/prod
                git clean -fd
            """

            output = await exec_shell_command(update_cmd)
            if len(output) > MAX_OUTPUT_LEN:
                output = output[:MAX_OUTPUT_LEN] + "\n... (truncated)"

            await send_interaction(
                interaction,
                content=f"```\n{output}\n```",
                ephemeral=True,
            )

            log_command_end(logger, "self_update", start_time)
        except Exception as exc:
            log_command_error(logger, "self_update", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while executing the command."
                )
            else:
                await interaction.followup.send("Error while executing the command.")
