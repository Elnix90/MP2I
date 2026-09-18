"""Ping command handlers.

Provides a `setup` function to register the `/ping` command which
returns the bot's gateway latency.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.config import cfg
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """
    Changes the model of the AI
    """

    @tree.command(name="model", description="Change le modèle d'IA que le bot utilise")
    async def model(interaction: discord.Interaction, model: str):
        start_time = time.perf_counter()
        log_command_start(logger, "model", interaction)

        try:
            cfg.AI_MODEL = model
            await interaction.response.send_message(f"Modèle changé! J'utilise maintenant : {model}")

            log_command_end(logger, "model", start_time)
        except Exception as exc:
            log_command_error(logger, "model", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message("Erreur: je n'ai pas réussi à changer de modèle")
            else:
                await interaction.followup.send("Error while changing model")
