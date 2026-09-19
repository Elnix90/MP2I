"""Ping command handlers.

Provides a `setup` function to register the `/ping` command which
returns the bot's gateway latency.
"""

import asyncio
import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.get_first_group_role import get_first_group_role
from core.motiver_colle import motiver_colle_msg
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """Mp the other member of the group to kick their ass"""

    @tree.command(
        name="get-to-work",
        description="Mp tes mate de groupe pour qu'ils se bougent le cul",
    )
    async def getToWork(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "getToWork", interaction)

        try:
            await interaction.response.defer(ephemeral=False)

            user = interaction.user

            group_role = get_first_group_role(user)

            if group_role is not None:
                # ALl the user's mates, not including himself
                mates = [member for member in group_role.members if member.id != user.id]

                if len(mates) == 0:
                    return await interaction.followup.send(
                        "Tu es tout seul dans ton groupe bro, force",
                    )
                if len(mates) == 1:
                    end_msg = "Je botte le cul à ton (seul) mate 👌\n-# Dcp je suis plus violent avec lui. Comme Gaudillat avec ceux qui passent au tableau"
                else:
                    end_msg = f"Je botte le cul à tes {len(mates)} mates 👌"

                for mate in mates:
                    try:
                        dm_message = motiver_colle_msg()
                        await mate.send(dm_message)
                        logger.info(f"Sent DM to {mate.display_name}: `{dm_message}`")
                    except discord.Forbidden:
                        logger.error(
                            f"Could not send DM to {mate.display_name} (DMs closed or bot blocked).",
                        )
                        end_msg = f"Je voulais leur botter le cul, mais <@{mate.id}> m'a bloqué!"
                    except Exception as e:
                        end_msg = f"Je voulais leur botter le cul, mais j'ai pas réussi pour <@{mate.id}>!"
                        logger.error(f"Error sending DM to {mate.display_name}: {e}")
                    # Respect Discord DM rate limits between sends.
                    await asyncio.sleep(0.5)

                await interaction.followup.send(end_msg)

            else:
                await interaction.followup.send(
                    "Bruh j'ai pas trouvé ton groupe, tu es un **INTRUS**, **BANNISEMMENT EN COURS**!!!",
                )

            log_command_end(logger, "getToWork", start_time)
        except Exception as exc:
            log_command_error(logger, "getToWork", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while checking your getToWorks.",
                )
            else:
                await interaction.followup.send("Error while checking getToWorks.")
