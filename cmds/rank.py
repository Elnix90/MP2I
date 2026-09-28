"""Delete a devoir surveillé and all its grades (admin only)."""

import time

import discord
from discord import app_commands

from bot import MP2IBot
from cmds._notes import autocomplete_ds
from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot: MP2IBot):
    @tree.command(
        name="rank",
        description="Donne ton rang dans ce DS",
    )
    @discord.app_commands.describe(ds="Pour quel DS veut tu savoir ton rang")
    async def rank(interaction: discord.Interaction, ds: str):
        start_time = time.perf_counter()
        log_command_start(logger, "rank", interaction, ds=ds)

        await defer_interaction(interaction, ephemeral=True)

        try:
            rank, notes_number = bot.notes.get_rank_for_ds(interaction.user.id, ds)

            if notes_number == 0:
                msg = "Il n'y a pas de notes sur ce ds"
            elif rank == -1:
                msg = "Tu n'as pas validé ta note sur ce DS, utilise `/note` pour le faire"
            elif rank == 0 and notes_number == 1:
                msg = "Tu es premier parmi 1, bravo champion!"
            else:
                msg = f"Tu es **#{rank + 1}** parmi les {notes_number} gens ayant validé leur note."

            await interaction.followup.send(msg)
            log_command_end(logger, "rank", start_time)

        except Exception as exc:
            log_command_error(logger, "rank", exc)
            await interaction.followup.send("Erreur interne (j'ai foiré le sql)")

    @rank.autocomplete("ds")
    async def ds_autocomplete(interaction: discord.Interaction, current: str):
        return autocomplete_ds(bot, current)
