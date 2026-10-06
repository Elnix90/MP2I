"""Model command handlers.

Registers the ``/ai model`` command to change the AI model at runtime. The choice
is persisted so it survives a bot restart.
"""

import time

import discord
from discord import app_commands

from cmds._groups import get_group
from cmds._shared import log_command_end, log_command_error, log_command_start
from core.ai import models as model_catalog
from core.config import cfg
from core.perms import is_bot_admin
from db.settings_store import set_setting
from utils.logger import get_logger

logger = get_logger()

_MAX_CHOICES = 25


def _model_choices(current: str) -> list[app_commands.Choice[str]]:
    """Active model first, then the free+healthy catalogue and configured fallbacks."""
    ids: list[str] = []

    def add(model_id: str) -> None:
        if model_id and model_id not in ids:
            ids.append(model_id)

    add(model_catalog.default_model())
    for model_id in model_catalog.candidates():
        add(model_id)
    for model_id in cfg.AI_MODELS:
        add(model_id)

    needle = current.strip().casefold()
    matched = [model_id for model_id in ids if needle in model_id.casefold()]
    return [app_commands.Choice(name=model_id[:100], value=model_id) for model_id in matched[:_MAX_CHOICES]]


async def setup(tree: app_commands.CommandTree, bot):
    ai = get_group(tree, "ai", description="Configuration de l'IA du bot")

    @ai.command(name="model", description="Change le modèle d'IA que le bot utilise")
    @app_commands.check(is_bot_admin)
    async def model(interaction: discord.Interaction, model: str):
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
                await interaction.followup.send("Erreur pendant le changement de modèle")

    @model.autocomplete("model")
    async def model_autocomplete(interaction: discord.Interaction, current: str):
        return _model_choices(current)
