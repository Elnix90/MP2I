"""Admin commands to manage the channels where the bot answers."""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.ai import load_allowed_channels, save_allowed_channels
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def _update_channel(interaction: discord.Interaction, *, allow: bool):
    command_name = "ai_allow" if allow else "ai_deny"
    start_time = time.perf_counter()
    log_command_start(logger, command_name, interaction)

    try:
        channel = interaction.channel
        if channel is None:
            return await interaction.response.send_message(
                "Cette commande doit être utilisée dans un salon.",
                ephemeral=True,
            )

        channels = load_allowed_channels()
        if allow and channel.id in channels:
            return await interaction.followup.send(
                f"Le bot répond déjà dans <#{channel.id}>.",
                ephemeral=True,
            )
        if not allow and channel.id not in channels:
            return await interaction.followup.send(
                f"Le bot ne répondait déjà pas dans <#{channel.id}>.",
                ephemeral=True,
            )

        if allow:
            channels.append(channel.id)
            save_allowed_channels(channels)
            await interaction.response.send_message(
                f"Le bot répondra maintenant dans <#{channel.id}>.",
            )
        else:
            channels.remove(channel.id)
            save_allowed_channels(channels)
            await interaction.response.send_message(
                f"Le bot ne répondra plus dans <#{channel.id}>.",
            )

        log_command_end(logger, command_name, start_time)
    except Exception as exc:
        log_command_error(logger, command_name, exc)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Error while running /{command_name}.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Error while running /{command_name}.",
                ephemeral=True,
            )


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="ai-allow",
        description="Autorise le bot IA à répondre dans ce salon (réservé aux admins)",
    )
    @app_commands.check(is_bot_admin)
    async def ai_allow(interaction: discord.Interaction):
        await _update_channel(interaction, allow=True)

    @tree.command(
        name="ai-deny",
        description="Empêche le bot IA de répondre dans ce salon (réservé aux admins)",
    )
    @app_commands.check(is_bot_admin)
    async def ai_deny(interaction: discord.Interaction):
        await _update_channel(interaction, allow=False)
