"""Permission predicates for Discord app commands."""

from discord import Interaction

from core.config import perms_cfg


def is_bot_admin(interaction: Interaction) -> bool:
    return interaction.user.id in perms_cfg.bot_admins
