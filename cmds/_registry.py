"""Command registry.

This module provides a centralized place to track all application commands,
making it easier to generate documentation and manage command loading.
"""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandInfo:
    name: str
    description: str
    module_name: str
    file_path: Path
    group: str | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.group} {self.name}" if self.group else self.name


def _literal_arg(call: ast.Call, keyword: str, position: int) -> str | None:
    for kw in call.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    if len(call.args) > position:
        arg = call.args[position]
        if isinstance(arg, ast.Constant):
            return str(arg.value)
    return None


def _collect_group_vars(tree: ast.AST) -> dict[str, str]:
    """Map local variables assigned via `x = get_group(tree, "name", ...)` to the group name."""
    group_vars: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if not (isinstance(func, ast.Name) and func.id == "get_group"):
            continue
        group_name = _literal_arg(node.value, "name", position=1)
        if group_name is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                group_vars[target.id] = group_name
    return group_vars


def get_all_commands() -> list[CommandInfo]:
    commands = []
    cmds_dir = Path(__file__).parent

    for file in cmds_dir.glob("*.py"):
        if file.name.startswith("_") or file.name == "loader.py":
            continue

        try:
            with open(file, encoding="utf-8") as f:
                tree = ast.parse(f.read())

            group_vars = _collect_group_vars(tree)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call):
                            func = decorator.func
                            is_command = False
                            receiver = None

                            # Matches @tree.command, @group.command or @app_commands.command
                            if isinstance(func, ast.Attribute) and func.attr == "command":
                                is_command = True
                                if isinstance(func.value, ast.Name):
                                    receiver = func.value.id
                            elif isinstance(func, ast.Name) and func.id == "command":
                                is_command = True

                            if is_command:
                                name = "unknown"
                                description = "No description provided"
                                for keyword in decorator.keywords:
                                    if keyword.arg == "name" and isinstance(
                                        keyword.value,
                                        ast.Constant,
                                    ):
                                        name = str(keyword.value.value)
                                    elif keyword.arg == "description" and isinstance(
                                        keyword.value,
                                        ast.Constant,
                                    ):
                                        description = str(keyword.value.value)

                                if name == "unknown":
                                    name = node.name

                                commands.append(
                                    CommandInfo(
                                        name=name,
                                        description=description,
                                        module_name=file.stem,
                                        file_path=file,
                                        group=group_vars.get(receiver) if receiver else None,
                                    ),
                                )
        except Exception:
            # Skip files that can't be parsed
            pass

    return sorted(commands, key=lambda x: x.qualified_name)
