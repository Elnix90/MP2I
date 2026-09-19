"""Delete a specific memory turn (owner or admin)."""

import time

import discord

from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
)
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot):
    """Register the ``memory-delete`` command."""

    @tree.command(
        name="memory-delete",
        description="Supprime un échange précis (son auteur ou un admin)",
    )
    @discord.app_commands.describe(turn_id="ID (ou préfixe) de l'échange à supprimer")
    async def memory_delete(interaction: discord.Interaction, turn_id: str):
        start_time = time.perf_counter()
        log_command_start(logger, "memory_delete", interaction, turn_id=turn_id)

        await defer_interaction(interaction)

        try:
            try:
                turn = bot.memory.get_turn(turn_id)
            except KeyError:
                await interaction.followup.send(
                    "ID d'échange introuvable.",
                    ephemeral=True,
                )
                log_command_end(logger, "memory_delete", start_time, status="not_found")
                return

            can_manage = (
                interaction.user.guild_permissions.manage_messages
                if interaction.guild
                else False
            )
            if turn.user_id != interaction.user.id and not can_manage:
                await interaction.followup.send(
                    "Tu n'as pas la permission de supprimer cet échange.",
                    ephemeral=True,
                )
                return

            deleted = await bot.memory.delete_turn_and_sync(turn.turn_id)
            await interaction.followup.send(
                f"Échange `{deleted.turn_id[:8]}` supprimé.",
                ephemeral=True,
            )
            log_command_end(logger, "memory_delete", start_time)
        except Exception as exc:
            log_command_error(logger, "memory_delete", exc)
            await interaction.followup.send(
                "Erreur pendant la suppression de l'échange.",
                ephemeral=True,
            )
