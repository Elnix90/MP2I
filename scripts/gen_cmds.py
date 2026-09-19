import re
import sys
from pathlib import Path

import json5

# Add project root to sys.path to import cmds._registry
sys.path.append(str(Path(__file__).parent.parent))

from cmds._registry import get_all_commands

PERM_LABELS = {
    "bot_admins": "Admins",
    "bot_users": "Tous les membres",
}


def load_permissions() -> dict[str, str]:
    perms_path = Path("config/perms.json5")
    if not perms_path.exists():
        return {}
    raw = json5.loads(perms_path.read_text(encoding="utf-8"))
    command_permissions = raw.get("command_permissions", {})
    return {name: ", ".join(str(PERM_LABELS.get(group, group)) for group in groups) for name, groups in command_permissions.items()}


def update_readme(commands):
    readme_path = Path("README.md")
    if not readme_path.exists():
        print("README.md not found")
        return

    permissions = load_permissions()

    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    commands_table = "| Command | Description | Permissions |\n| :--- | :--- | :--- |\n"
    for cmd in commands:
        perms = permissions.get(cmd.name, "—")
        commands_table += f"| `/{cmd.name}` | {cmd.description} | {perms} |\n"

    new_content = re.sub(
        r"<!-- COMMANDS-START -->.*?<!-- COMMANDS-END -->",
        f"<!-- COMMANDS-START -->\n{commands_table}\n<!-- COMMANDS-END -->",
        content,
        flags=re.DOTALL,
    )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Updated README.md with {len(commands)} commands.")


if __name__ == "__main__":
    commands = get_all_commands()
    update_readme(commands)
