"""Remove a grade by its id (admin only)."""

import time

import discord

from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot):
    @tree.command(
        name="note-remove",
        description="Supprime une note par son identifiant (admin)",
    )
    @discord.app_commands.describe(
        note_id="Identifiant de la note",
    )
    @discord.app_commands.check(is_bot_admin)
    async def note_remove(interaction: discord.Interaction, note_id: int):
        start_time = time.perf_counter()
        log_command_start(logger, "note_remove", interaction, note_id=note_id)

        await defer_interaction(interaction, ephemeral=True)

        try:
            removed = bot.notes.remove_note(note_id)
            if not removed:
                await interaction.followup.send(f"Note `{note_id}` introuvable")
                log_command_end(logger, "note_remove", start_time, status="not_found")
                return

            await interaction.followup.send(f"Note `{note_id}` supprimée")
            log_command_end(logger, "note_remove", start_time)
        except Exception as exc:
            log_command_error(logger, "note_remove", exc)
            await interaction.followup.send("Erreur pendant la suppression de la note")
