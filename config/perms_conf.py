"""Permission configuration loading helpers."""

from dataclasses import dataclass, field
from pathlib import Path

import json5


@dataclass
class PermsConfig:
    bot_admins: list[int] = field(default_factory=list)
    blacklist: list[int] = field(default_factory=list)
    command_permissions: dict[str, list[str]] = field(default_factory=dict)


def load_perms_config(file: Path | None = None) -> PermsConfig:
    path = file or Path("config/perms.json5")
    with open(path) as f:
        raw = json5.load(f)

    perms_raw = raw.get("perms", raw)

    return PermsConfig(
        bot_admins=perms_raw.get("bot_admins", []),
        blacklist=perms_raw.get("blacklist", []),
        command_permissions=perms_raw.get("command_permissions", {}),
    )
