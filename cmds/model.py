"""Model command handlers.

Registers the ``/model`` command to change the AI model at runtime. The choice
is persisted so it survives a bot restart.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.config import cfg
from db.settings_store import set_setting
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """Register the ``model`` command on the given command tree."""

    @tree.command(name="model", description="Change le modèle d'IA que le bot utilise")
    async def model(interaction: discord.Interaction, model: str):
        """Change the active AI model and persist the choice."""
        start_time = time.perf_counter()
        log_command_start(logger, "model", interaction)

        try:
            cfg.AI_MODEL = model
            set_setting("ai.model", model)
            await interaction.response.send_message(
                f"Modèle changé ! J'utilise maintenant : {model}",
            )
            log_command_end(logger, "model", start_time)
        except Exception as exc:
            log_command_error(logger, "model", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Erreur : je n'ai pas réussi à changer de modèle",
                )
            else:
                await interaction.followup.send(
                    "Erreur pendant le changement de modèle"
                )
