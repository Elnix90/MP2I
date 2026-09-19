"""Ping command handlers.

Provides a `setup` function to register the `/ping` command which
returns the bot's gateway latency.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.config import cfg
from core.get_first_group_role import get_first_group_role
from db.sql_requests import get_colles
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: app_commands.CommandTree, bot):
    """Returns the colles of the week for the user issuing the command"""

    @tree.command(
        name="colle",
        description="Renvoie les colles de la semaine pour l'utilisateur",
    )
    async def colle(interaction: discord.Interaction, user: discord.User | None = None, semaine_id: int | None = None):
        start_time = time.perf_counter()
        log_command_start(logger, "colle", interaction)

        try:
            if user is not None:
                user_requested = user
            else:
                user_requested = interaction.user

            group_role = get_first_group_role(user_requested)

            msg = "Bruh, j'ai pas trouvé ton groupe, tu es un **INTRUS**, ***BANNISEMMENT EN COURS***!!!"

            if group_role is not None:
                role_number = cfg.GROUPS_CONFIG.role_id_to_number.get(group_role.id)
                if role_number is not None:
                    colle_result = get_colles(role_number, semaine_id)

                    if colle_result:
                        colles_str = "\n".join(f"- {colle}" for colle in colle_result.colles)

                        if user is not None:
                            user_str = f"{user_requested.mention} du **{group_role.name}** aura"
                            user_suffix = "\n-# est ce qu'il était bien consentant à ce que tu vérifie ses colles?"
                        else:
                            user_str = "tu auras"
                            user_suffix = ""

                        msg = f"{colle_result.week_str()}, {user_str} ces colles:\n{colles_str}{user_suffix}"
                    else:
                        msg = f"Aucune colle cette semaine pour le **{group_role.name}**"

            await interaction.response.send_message(content=msg)

            log_command_end(logger, "colle", start_time)
        except Exception as exc:
            log_command_error(logger, "colle", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Je n'ai pas réussi à obtenir les colles: {exc}")
            else:
                await interaction.followup.send("Error while checking colles.")
