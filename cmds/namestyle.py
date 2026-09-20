"""Namestyle command handler.

Registers the ``/namestyle`` command to change the bot's display name style
(font, effect, colors) in the current guild using Discord's nameplate API.
"""

import time

import discord
from discord import app_commands

from cmds._shared import log_command_end, log_command_error, log_command_start
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()

FONT_CHOICES = [
    app_commands.Choice(name="Default", value=11),
    app_commands.Choice(name="Tempo", value=1),
    app_commands.Choice(name="Sakura", value=3),
    app_commands.Choice(name="Jellybean", value=4),
    app_commands.Choice(name="Modern", value=6),
    app_commands.Choice(name="Medieval", value=7),
    app_commands.Choice(name="8bit", value=8),
    app_commands.Choice(name="Vampyre", value=10),
]

EFFECT_CHOICES = [
    app_commands.Choice(name="Solid", value=1),
    app_commands.Choice(name="Gradient", value=2),
    app_commands.Choice(name="Neon", value=3),
    app_commands.Choice(name="Toon", value=4),
    app_commands.Choice(name="Pop", value=5),
    app_commands.Choice(name="Glow", value=6),
    app_commands.Choice(name="Reset", value=0),
]


def _hex_to_decimal(hex_str: str) -> int:
    return int(hex_str.lstrip("#"), 16)


async def setup(tree: app_commands.CommandTree, bot: discord.Client):
    @tree.command(name="namestyle", description="Change le style d'affichage du bot dans ce serveur")
    @app_commands.describe(
        font="Police du nom (ex: Sakura, Medieval, 8bit...)",
        effect="Effet visuel (Solid, Gradient, Neon...)",
        color1="Couleur hex (ex: #FF69B4)",
        color2="2e couleur hex pour le gradient (ex: #8B17E4)",
    )
    @app_commands.choices(font=FONT_CHOICES, effect=EFFECT_CHOICES)
    @app_commands.check(is_bot_admin)
    async def namestyle(
        interaction: discord.Interaction,
        font: app_commands.Choice[int],
        effect: app_commands.Choice[int],
        color1: str,
        color2: str | None = None,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "namestyle", interaction, font=font.name, effect=effect.name)

        try:
            colors = [_hex_to_decimal(color1)]
            if effect.value == 2:
                if not color2:
                    await interaction.response.send_message(
                        "L'effet Gradient nécessite 2 couleurs.",
                        ephemeral=True,
                    )
                    return
                colors.append(_hex_to_decimal(color2))
            elif color2:
                await interaction.response.send_message(
                    "La 2e couleur n'est utilisée que pour l'effet Gradient.",
                    ephemeral=True,
                )
                return

            payload = {
                "display_name_font_id": font.value,
                "display_name_effect_id": effect.value,
                "display_name_colors": colors,
            }

            route = discord.http.Route("PATCH", f"/guilds/{interaction.guild_id}/members/@me")  # type: ignore[attr-defined]
            await bot.http.request(route, json=payload)

            await interaction.response.send_message(
                f"Style appliqué ! Police **{font.name}**, effet **{effect.name}**, couleur(s) `{color1}`" + (f" + `{color2}`" if color2 else ""),
            )
            log_command_end(logger, "namestyle", start_time)
        except discord.Forbidden:
            log_command_error(logger, "namestyle", ForbiddenError())
            await interaction.response.send_message(
                "Permission refusée : vérifie que le bot a le droit de changer son surnom.",
                ephemeral=True,
            )
        except Exception as exc:
            log_command_error(logger, "namestyle", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Erreur : {exc}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(f"Erreur : {exc}")


class ForbiddenError(Exception):
    pass
