"""List grades, optionally filtered by user or DS."""

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
        name="note-list",
        description="Affiche les notes des élèves, triées par DS",
    )
    @discord.app_commands.describe(
        user="Filtrer par élève (optionnel)",
        ds="Filtrer par devoir surveillé (optionnel)",
    )
    @app_commands.check(is_bot_admin)
    async def note_list(
        interaction: discord.Interaction,
        user: discord.User | None = None,
        ds: str | None = None,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "note_list", interaction, user=user.id if user else None, ds=ds)

        await defer_interaction(interaction, ephemeral=True)

        try:
            notes = bot.notes.list_notes()
            if user is not None:
                notes = [n for n in notes if n.user_id == user.id]
            if ds is not None:
                found = bot.notes.get_ds_by_name(ds)
                if found is None:
                    await interaction.followup.send(f"DS {ds} introuvable")
                    log_command_end(logger, "note_list", start_time, status="ds_not_found")
                    return
                notes = [n for n in notes if n.ds_id == found.id]

            if not notes:
                await interaction.followup.send("Aucune note trouvée")
                log_command_end(logger, "note_list", start_time, status="empty")
                return

            ds_names = {d.id: d for d in bot.notes.list_ds()}

            lines: list[str] = []
            current_ds = None
            for note in notes:
                if note.ds_id != current_ds:
                    current_ds = note.ds_id
                    lines.append(f"\n**{ds_names.get(current_ds, current_ds)}**")
                lines.append(f"- <@{note.user_id}> : **{note.note:g} / 20** `(#{note.id})`")

            content = "\n".join(lines).strip()
            await interaction.followup.send(content)
            log_command_end(logger, "note_list", start_time)
        except Exception as exc:
            log_command_error(logger, "note_list", exc)
            await interaction.followup.send("Erreur pendant la lecture des notes")

    @note_list.autocomplete("ds")
    async def ds_autocomplete(interaction: discord.Interaction, current: str):
        return autocomplete_ds(bot, current)
