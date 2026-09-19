from dataclasses import dataclass, field
from pathlib import Path

import json5


@dataclass
class GroupsConfig:
    groups: dict[int, int]
    role_id_to_number: dict[int, int] = field(init=False)

    def __post_init__(self):
        self.role_id_to_number = {role_id: n for n, role_id in self.groups.items()}


def load_groups_config(file: Path | None = None) -> GroupsConfig:
    path = file or Path("config/group_ids.json5")
    with open(path) as f:
        raw = json5.load(f)

    return GroupsConfig(raw)
