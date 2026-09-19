"""Admin commands to configure the AI on a per-channel basis.

Channels can be set to ``normal`` mode (reply in-channel on mention, with
channel-scoped memory) or ``thread`` mode (mention starts a thread, per-thread
memory). Unconfigured channels are ignored by the bot.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.ai.channels import remove_channel, set_channel_mode
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def _set_mode(
    interaction: discord.Interaction,
    mode: str,
    channel: discord.TextChannel | discord.Thread | None,
):
    command_name = f"ai_{mode}_mode"
    start_time = time.perf_counter()
    log_command_start(logger, command_name, interaction, mode=mode)

    try:
        target = channel or interaction.channel
        if target is None or target.id is None:
            return await interaction.response.send_message(
                "Impossible de déterminer le salon cible.",
                ephemeral=True,
            )

        set_channel_mode(target.id, mode)
        await interaction.response.send_message(
            f"Mode IA de <#{target.id}> réglé sur **{mode}**.",
            ephemeral=True,
        )
        log_command_end(logger, command_name, start_time)
    except Exception as exc:
        log_command_error(logger, command_name, exc)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Erreur lors du réglage du mode IA.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Erreur lors du réglage du mode IA.",
                ephemeral=True,
            )


async def _deny_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel | discord.Thread | None,
):
    command_name = "ai_deny"
    start_time = time.perf_counter()
    log_command_start(logger, command_name, interaction)

    try:
        target = channel or interaction.channel
        if target is None or target.id is None:
            return await interaction.response.send_message(
                "Impossible de déterminer le salon cible.",
                ephemeral=True,
            )

        removed = remove_channel(target.id)
        message = (
            f"Le bot n'interagira plus dans <#{target.id}>."
            if removed
            else f"Le bot n'était déjà pas configuré dans <#{target.id}>."
        )
        await interaction.response.send_message(message, ephemeral=True)
        log_command_end(logger, command_name, start_time)
    except Exception as exc:
        log_command_error(logger, command_name, exc)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Erreur lors de la désactivation.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Erreur lors de la désactivation.",
                ephemeral=True,
            )


async def _list_channels(interaction: discord.Interaction):
    command_name = "ai_list"
    start_time = time.perf_counter()
    log_command_start(logger, command_name, interaction)

    try:
        from core.ai.channels import load_channel_modes

        modes = load_channel_modes()
        if not modes:
            content = "Aucun salon configuré pour l'IA."
        else:
            lines = [
                f"`{channel_id}` → **{mode}**" for channel_id, mode in modes.items()
            ]
            content = "Salons configurés pour l'IA :\n" + "\n".join(lines)

        await interaction.response.send_message(content, ephemeral=True)
        log_command_end(logger, command_name, start_time)
    except Exception as exc:
        log_command_error(logger, command_name, exc)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Erreur lors de la liste des salons.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Erreur lors de la liste des salons.",
                ephemeral=True,
            )


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="ai",
        description="Configure le mode IA d'un salon (admin)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        action="Action à effectuer",
        channel="Salon cible (par défaut : celui-ci)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="normal_mode", value="normal"),
            app_commands.Choice(name="thread_mode", value="thread"),
            app_commands.Choice(name="deny", value="deny"),
            app_commands.Choice(name="list", value="list"),
        ]
    )
    async def ai_command(
        interaction: discord.Interaction,
        action: str,
        channel: discord.TextChannel | discord.Thread | None = None,
    ):
        if not is_bot_admin(interaction):
            await interaction.response.send_message(
                "Tu n'as pas la permission d'utiliser cette commande.",
                ephemeral=True,
            )
            return

        if action == "deny":
            await _deny_channel(interaction, channel)
        elif action == "list":
            await _list_channels(interaction)
        elif action in ("normal", "thread"):
            await _set_mode(interaction, action, channel)
        else:
            await interaction.response.send_message(
                f"Action inconnue : {action}",
                ephemeral=True,
            )
