from dataclasses import dataclass, field
from pathlib import Path

import json5


@dataclass
class GroupsConfig:
    groups: dict[int, int]
    role_id_to_number: dict[int, int] = field(init=False)

    def __post_init__(self):
        # json5 yields str keys/values, coerce them to the declared int types.
        self.groups = {int(number): int(role_id) for number, role_id in self.groups.items()}
        self.role_id_to_number = {role_id: number for number, role_id in self.groups.items()}


def load_groups_config(file: Path | None = None) -> GroupsConfig:
    path = file or Path("config/group_ids.json5")
    with open(path) as f:
        raw = json5.load(f)

    return GroupsConfig(raw)
