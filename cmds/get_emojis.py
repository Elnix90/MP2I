"""Shell command handler.

Provides a `setup` function to register the `/get-emojis_sh` command which runs
a shell command on the bot's host and returns its output.
"""

import time

import discord
from discord import app_commands

from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start, send_interaction
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="get-emojis",
        description="Prints all the server's emojis",
    )
    async def get_emojis(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "get-emojis", interaction)

        try:
            await defer_interaction(interaction)

            guild = interaction.guild
            if guild is None:
                return await send_interaction(interaction=interaction, content="You must use this command in a server")

            msg = "".join([str(emoji) for emoji in guild.emojis])

            await send_interaction(interaction, content=msg)

            log_command_end(logger, "get-emojis", start_time)
        except Exception as exc:
            log_command_error(logger, "get-emojis", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Je n'ai pas réussi à trouver les émojis du serveur",
                )
            else:
                await interaction.followup.send("Error while getting emojis.")
