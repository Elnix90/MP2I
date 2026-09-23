"""Shared helpers for notes-related commands."""

from discord import app_commands


def autocomplete_ds(bot, current: str) -> list[app_commands.Choice]:
    name = current.lower()
    choices = [app_commands.Choice(name=ds.name, value=ds.name) for ds in sorted(bot.notes.list_ds(), key=lambda d: d.name.lower()) if name in ds.name.lower()]
    return choices[:25]
