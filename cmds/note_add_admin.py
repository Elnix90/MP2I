"""Add a grade for a user on a DS (admin only)."""

import time

import discord
from discord import app_commands

from cmds._notes import autocomplete_ds
from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="note-add-admin",
        description="Ajoute une note à un élève sur un DS (admin)",
    )
    @app_commands.check(is_bot_admin)
    @discord.app_commands.describe(
        user="Élève concerné",
        ds="Devoir surveillé",
        note="Note obtenue",
    )
    async def note_add_admin(
        interaction: discord.Interaction,
        user: discord.User,
        ds: str,
        note: app_commands.Range[float, 0.0, 100.0],
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "note_add", interaction, user=user.id, ds=ds, note=note)

        await defer_interaction(interaction, ephemeral=True)

        try:
            found = bot.notes.get_ds_by_name(ds)
            if found is None:
                await interaction.followup.send(f"DS {ds} introuvable. Utilise `/ds-list` pour voir les DS existants")
                log_command_end(logger, "note_add", start_time, status="ds_not_found")
                return

            note_id = bot.notes.add_note(user, note, found.id)
            await interaction.followup.send(f"Note **{note:g}** ajoutée pour {user.mention} sur le DS {found} (id `{note_id}`)")
            log_command_end(logger, "note_add", start_time)
        except Exception as exc:
            log_command_error(logger, "note_add", exc)
            await interaction.followup.send("Erreur pendant l'ajout de la note")

    @note_add_admin.autocomplete("ds")
    async def ds_autocomplete(interaction: discord.Interaction, current: str):
        return autocomplete_ds(bot, current)
