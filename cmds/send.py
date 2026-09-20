"""Send command handler.

Provides a `setup` function to register the `/send` command which creates a
temporary webhook impersonating a member (name + avatar) to post a custom
message in the current channel (or another one), then deletes the webhook.
Restricted to bot admins (see config/perms.json5).
"""

import time

import discord
from discord import app_commands

from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
    send_interaction,
)
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(name="send")
    @app_commands.check(is_bot_admin)
    async def send(
        interaction: discord.Interaction,
        message: str,
        user: discord.User | None = None,
        channel: discord.TextChannel | discord.Thread | None = None,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "send", interaction)

        target: discord.TextChannel | discord.Thread | None = None
        target_id: int | None = None

        try:
            await defer_interaction(interaction, ephemeral=True)

            target = channel
            if target is None:
                candidate = interaction.channel
                if isinstance(candidate, (discord.TextChannel, discord.Thread)):
                    target = candidate

            if target is None:
                await send_interaction(
                    interaction,
                    content="Impossible d'envoyer le message : aucun salon cible trouvé.",
                    ephemeral=True,
                )
                return

            target_id = target.id
            impersonated: discord.User | discord.Member = user or interaction.user

            hook_source: discord.TextChannel | discord.ForumChannel
            if isinstance(target, discord.Thread):
                if target.parent is None:
                    await send_interaction(
                        interaction,
                        content="Impossible d'envoyer le message : salon parent introuvable.",
                        ephemeral=True,
                    )
                    return
                hook_source = target.parent
            else:
                hook_source = target

            webhook = await hook_source.create_webhook(name=impersonated.display_name[:80])

            try:
                await webhook.send(
                    message,
                    username=impersonated.display_name,
                    avatar_url=impersonated.display_avatar.url,
                    thread=target if isinstance(target, discord.Thread) else discord.utils.MISSING,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False,
                        roles=False,
                        users=True,
                    ),
                )
            finally:
                await webhook.delete()

            logger.info(
                "Sent message in <#%s> impersonating %s (id=%s)",
                target.id,
                impersonated.display_name,
                impersonated.id,
            )

            await send_interaction(
                interaction,
                content=f"Message envoyé dans <#{target.id}> en tant que **{impersonated.display_name}**.",
                ephemeral=True,
            )

            log_command_end(logger, "send", start_time)
        except discord.Forbidden:
            logger.error(
                "Missing permission to create webhooks in channel %s",
                target_id,
            )
            await send_interaction(
                interaction,
                content="Le bot n'a pas la permission de créer des webhooks dans ce salon.",
                ephemeral=True,
            )
        except Exception as exc:
            log_command_error(logger, "send", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while sending the message.",
                )
            else:
                await interaction.followup.send("Error while sending the message.")
