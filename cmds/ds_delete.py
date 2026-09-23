"""Delete a devoir surveillé and all its grades (admin only)."""

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
        name="ds-delete",
        description="Supprime un DS et toutes ses notes (admin)",
    )
    @discord.app_commands.describe(ds="Devoir surveillé à supprimer")
    @discord.app_commands.check(is_bot_admin)
    async def ds_delete(interaction: discord.Interaction, ds: str):
        start_time = time.perf_counter()
        log_command_start(logger, "ds_delete", interaction, ds=ds)

        await defer_interaction(interaction)

        try:
            found = bot.notes.get_ds_by_name(ds)
            if found is None:
                await interaction.followup.send(
                    f"DS {ds} introuvable.",
                    ephemeral=True,
                )
                log_command_end(logger, "ds_delete", start_time, status="ds_not_found")
                return

            notes_removed = bot.notes.delete_ds(found.id)
            plural = "s" if len(notes_removed) > 1 else ""
            await interaction.followup.send(f"DS {found} supprimé ({notes_removed} note{plural} associée{plural}).")
            log_command_end(logger, "ds_delete", start_time)

        except Exception as exc:
            log_command_error(logger, "ds_delete", exc)
            await interaction.followup.send(
                "Erreur pendant la suppression du DS.",
                ephemeral=True,
            )

    @ds_delete.autocomplete("ds")
    async def ds_autocomplete(interaction: discord.Interaction, current: str):
        return autocomplete_ds(bot, current)
