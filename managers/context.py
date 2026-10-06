"""Helpers to gather and format Discord server context.

Provides utilities to collect basic server metadata and format it for
inclusion in system prompts.
"""

from pathlib import Path

import discord
from attr import dataclass, field
from discord.emoji import Emoji

from utils.logger import get_logger

logger = get_logger()


@dataclass
class ServerEmojis:
    """Custom server emojis paired with an optional description file."""

    emojis: list[Emoji] = field(factory=list)
    emojis_desc_filepath: Path | None = None
    emojis_desc: list[str] | None = None
    emojis_with_desc: list[tuple[Emoji, str]] | None = None

    def read_emojis_desc(self) -> None:
        """Load one description per line from `emojis_desc_filepath`."""
        if self.emojis_desc_filepath is None:
            return
        with self.emojis_desc_filepath.open(encoding="utf-8") as f:
            self.emojis_desc = [line.strip() for line in f if line.strip()]

    def bind(self) -> None:
        """Pair each emoji with the description at the same index."""
        if not self.emojis_desc:
            self.emojis_with_desc = None
            return
        self.emojis_with_desc = list(zip(self.emojis, self.emojis_desc))


@dataclass
class ServerContext:
    server_name: str
    server_desc: str
    member_count: int
    server_emojis: tuple[Emoji, ...]
    replying_to: str | None = None

    def __str__(self) -> str:
        lines = [
            f"Information about the current Discord server '{self.server_name}':",
            f"    - Server description: {self.server_desc}",
            f"    - Total member count: {self.member_count}",
            f"    - Server Emojis: {', '.join(str(emoji) for emoji in self.server_emojis)}",
        ]
        if self.replying_to:
            lines.append(f"    - The user is replying to: {self.replying_to}")
        return "\n".join(lines)


async def get_server_context(guild: discord.Guild, replying_to: str | None = None) -> ServerContext:
    return ServerContext(
        server_name=guild.name,
        server_desc=guild.description or "",
        member_count=guild.member_count or 0,
        server_emojis=guild.emojis,
        replying_to=replying_to,
    )
