"""Add a devoir surveillé (admin only)."""

import sqlite3
import time

import discord
from discord import app_commands

from bot import MP2IBot
from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start
from core.perms import is_bot_admin
from managers.notes import Ds
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot: MP2IBot):
    @tree.command(
        name="ds-add",
        description="Ajoute un devoir surveillé (admin)",
    )
    @discord.app_commands.describe(name="Nom du DS")
    @discord.app_commands.check(is_bot_admin)
    async def ds_add(interaction: discord.Interaction, name: str):
        start_time = time.perf_counter()
        log_command_start(logger, "ds_add", interaction, name=name)

        await defer_interaction(interaction)

        try:
            ds_id = bot.notes.add_new_ds(name)
            ds = Ds(ds_id, name)
            await interaction.followup.send(f"{ds} ajouté!")
            log_command_end(logger, "ds_add", start_time)
        except sqlite3.IntegrityError:
            await interaction.followup.send(
                f"Un DS nommé {name} existe déjà.",
                ephemeral=True,
            )
            log_command_end(logger, "ds_add", start_time, status="duplicate")
        except Exception as exc:
            log_command_error(logger, "ds_add", exc)
            await interaction.followup.send(
                "Erreur pendant l'ajout du DS.",
                ephemeral=True,
            )
