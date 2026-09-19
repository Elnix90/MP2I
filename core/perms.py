"""Permission predicates for Discord app commands."""

from discord import Interaction

from core.config import perms_cfg


def is_bot_admin(interaction: Interaction) -> bool:
    return interaction.user.id in perms_cfg.bot_admins


def is_blacklisted_user_id(user_id: int) -> bool:
    """Return True when the user id is on the global blacklist."""
    return user_id in perms_cfg.blacklist


def is_blacklisted(interaction: Interaction) -> bool:
    return is_blacklisted_user_id(interaction.user.id)
