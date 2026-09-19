"""Clear the memory of the current conversation scope (admin only)."""

import time

import discord

from cmds._memory import interaction_scope
from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot):
    @tree.command(
        name="memory-clear",
        description="Efface la mémoire de la conversation actuelle (admin)",
    )
    async def memory_clear(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "memory_clear", interaction)

        if not is_bot_admin(interaction):
            await interaction.response.send_message(
                "Tu n'as pas la permission d'effacer la mémoire de ce salon.",
                ephemeral=True,
            )
            return

        await defer_interaction(interaction)

        try:
            scope = interaction_scope(interaction)
            removed = await bot.memory.clear_history_and_sync(scope)
            await interaction.followup.send(
                f"{removed} échange(s) supprimé(s) pour ce salon.",
                ephemeral=True,
            )
            log_command_end(logger, "memory_clear", start_time)
        except Exception as exc:
            log_command_error(logger, "memory_clear", exc)
            await interaction.followup.send(
                "Erreur pendant l'effacement de la mémoire.",
                ephemeral=True,
            )
