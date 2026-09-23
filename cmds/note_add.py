"""Add a grade for a user on a DS (admin only)."""

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
        name="note",
        description="Ajoute ta note sur un DS",
    )
    @discord.app_commands.describe(
        ds="Devoir surveillé",
        note="Note obtenue",
    )
    async def note_add(
        interaction: discord.Interaction,
        ds: str,
        note: app_commands.Range[float, 0.0, 100.0],
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "note_add", interaction, ds=ds, note=note)

        await defer_interaction(interaction, ephemeral=True)

        user = interaction.user
        try:
            found = bot.notes.get_ds_by_name(ds)
            if found is None:
                await interaction.followup.send(f"DS {ds} introuvable. Utilise `/ds-list` pour voir les DS existants")
                log_command_end(logger, "note_add", start_time, status="ds_not_found")
                return

            note_id = bot.notes.add_note(user, note, found.id)

            await interaction.followup.send(f"Ta note de {'(merde)' if note < 5 else ''} **{note:g}** a étée ajoutée sur le DS {found} (id `{note_id}`)")
            log_command_end(logger, "note_add", start_time)
        except Exception as exc:
            log_command_error(logger, "note_add", exc)
            await interaction.followup.send("Erreur pendant l'ajout de la note")

    @note_add.autocomplete("ds")
    async def ds_autocomplete(interaction: discord.Interaction, current: str):
        return autocomplete_ds(bot, current)
