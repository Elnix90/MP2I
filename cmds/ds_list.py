"""List all devoirs surveillés."""

import time

import discord

from bot import MP2IBot
from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot: MP2IBot):
    @tree.command(
        name="ds-list",
        description="Affiche les devoirs surveillés enregistrés",
    )
    async def ds_list(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "ds_list", interaction)

        await defer_interaction(interaction)

        try:
            dss = bot.notes.list_ds()
            if not dss:
                await interaction.followup.send(
                    "Aucun DS enregistré.",
                    ephemeral=True,
                )
                log_command_end(logger, "ds_list", start_time, status="empty")
                return

            notes = bot.notes.list_notes()
            counts = {ds.id: sum(1 for n in notes if n.ds_id == ds.id) for ds in dss}

            content = "\n".join(f"{ds.id}. {ds} - {counts[ds.id]} note{'s' if counts[ds.id] > 1 else ''}" for ds in dss)
            await interaction.followup.send(content)
            log_command_end(logger, "ds_list", start_time)
        except Exception as exc:
            log_command_error(logger, "ds_list", exc)
            await interaction.followup.send(
                "Erreur pendant la lecture des DS.",
                ephemeral=True,
            )
