"""Shared helpers for Discord application command groups."""

from discord import app_commands


def get_group(tree: app_commands.CommandTree, name: str, *, description: str) -> app_commands.Group:
    """Return the top-level group `name`, creating and registering it once.

    Multiple command modules can call this to attach their subcommands to the
    same group regardless of load order.
    """
    existing = tree.get_command(name)
    if isinstance(existing, app_commands.Group):
        return existing
    if existing is not None:
        raise ValueError(f"Command {name!r} already registered and is not a group")
    group = app_commands.Group(name=name, description=description)
    tree.add_command(group)
    return group
