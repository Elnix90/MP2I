"""List recent memory turns for the current conversation scope."""

import time

import discord

from cmds._memory import interaction_scope
from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
)
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot):
    """Register the ``memory-list`` command."""

    @tree.command(
        name="memory-list", description="Affiche les derniers échanges en mémoire"
    )
    @discord.app_commands.describe(
        limit="Nombre d'échanges à afficher", user="Filtrer par utilisateur (optionnel)"
    )
    async def memory_list(
        interaction: discord.Interaction,
        limit: int = 10,
        user: discord.User | None = None,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "memory_list", interaction, limit=limit)

        await defer_interaction(interaction)

        try:
            scope = interaction_scope(interaction)
            turns = bot.memory.list_turns(scope, limit=max(1, min(limit, 20)))
            if user is not None:
                turns = [t for t in turns if t.user_id == user.id]

            if not turns:
                await interaction.followup.send(
                    "Aucun échange en mémoire pour ce salon.",
                    ephemeral=True,
                )
                log_command_end(logger, "memory_list", start_time, status="empty")
                return

            def _format_turn(turn) -> str:
                created = time.strftime(
                    "%Y-%m-%d %H:%M:%S", time.localtime(turn.created_at)
                )
                user_snippet = turn.user_content.replace("\n", " ")[:120]
                assistant_snippet = (turn.assistant_content or "").replace("\n", " ")[
                    :120
                ]
                lines = [
                    f"{turn.turn_id[:8]} | {created} | {turn.user_name} ({turn.user_id})",
                    f"  user: {user_snippet}",
                ]
                if assistant_snippet:
                    lines.append(f"  bot: {assistant_snippet}")
                return "\n".join(lines)

            content = "\n\n".join(_format_turn(turn) for turn in turns)
            if len(content) > 1900:
                content = content[:1900] + "\n..."
            await interaction.followup.send(
                f"```text\n{content}\n```",
                ephemeral=True,
            )
            log_command_end(logger, "memory_list", start_time)
        except Exception as exc:
            log_command_error(logger, "memory_list", exc)
            await interaction.followup.send(
                "Erreur pendant la lecture de la mémoire.",
                ephemeral=True,
            )
