"""Ping command handlers.

Provides a `setup` function to register the `/ping` command which
returns the bot's gateway latency.
"""

import time

import discord
from discord import Role, app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.get_first_group_role import get_first_group_role
from core.roles_ids import ROLES_IDS
from db.sql_requests import get_colles
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """
    Returns the colles of the week for the user issuing the command
    """

    @tree.command(name="colle", description="Renvoie les colles de la semaine pour l'utilisateur")
    async def colle(interaction: discord.Interaction, user: discord.User | None = None):
        """Respond with gateway latency.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction that triggered the command.
        """

        start_time = time.perf_counter()
        log_command_start(logger, "colle", interaction)

        try:
            if user is not None:
                user_requested = user
            else:
                user_requested = interaction.user

            group_role = get_first_group_role(user_requested)

            if group_role is not None:
                role_number = list(ROLES_IDS.keys())[list(ROLES_IDS.values()).index(group_role.id)]
                colles = get_colles(role_number)

                colles_str = f"\n- {colles[0]}\n- {colles[1]}"

                if user is not None:
                    msg = f"{user_requested.mention} du groupe {group_role.mention} aura ces colles cette semaine: {colles_str}\n-# est ce qu'il était bien consentant à ce que tu vérifie ses colles?"
                else:
                    msg = f"Hello {user_requested.mention}, tu fais parti du {group_role.mention}\nTes colles sont:{colles_str}"
            else:
                msg = "Bruh j'ai pas trouvé ton groupe, tu es un **INTRUS**, **BANNISEMMENT EN COURS**!!!"

            await interaction.response.send_message(content=msg)

            log_command_end(logger, "colle", start_time)
        except Exception as exc:
            log_command_error(logger, "colle", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message("Error while checking your colles.")
            else:
                await interaction.followup.send("Error while checking colles.")
