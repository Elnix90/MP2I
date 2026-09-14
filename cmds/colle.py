"""Ping command handlers.

Provides a `setup` function to register the `/ping` command which
returns the bot's gateway latency.
"""

import time

import discord
from discord import Role, app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from data.roles_ids import ROLES_IDS
from db.sql_requests import get_colle
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """
    Returns the colles of the week for the user issuing the command
    """

    @tree.command(name="colle", description="Renvoie les colles de la semaine pour l'utilisateur")
    async def colle(interaction: discord.Interaction):
        """Respond with gateway latency.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction that triggered the command.
        """

        start_time = time.perf_counter()
        log_command_start(logger, "colle", interaction)

        try:
            user = interaction.user.id

            roles: list[Role] = interaction.user.roles  # pyright: ignore[reportAttributeAccessIssue]
            roles_list: list[int] = [role.id for role in roles]

            user_group: int | None = None
            user_group_role_id: int | None = None
            
            group_roles_number: int = 0

            for group, role_id in ROLES_IDS.items():
                if role_id in roles_list:
                    user_group, user_group_role_id = group, role_id
                    group_roles_number += 1

            if user_group is not None and user_group_role_id is not None:

                colle = get_colle(user_group)
                
                
                msg = f"Hello <@{user}>, tu fais parti du Groupe {user_group}! (<@&{user_group_role_id}>)\nta colle est: {colle}"
            else:
                msg = "Bruh j'ai pas trouvé ton groupe, tu es un **INTRU**, **BANNISEMMENT EN COURS**!!!"

            await interaction.response.send_message(content = msg)

            log_command_end(logger, "colle", start_time)
        except Exception as exc:
            log_command_error(logger, "colle", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while checking your colles.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Error while checking colles.", ephemeral=True
                )
