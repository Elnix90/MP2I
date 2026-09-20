"""Tool loading helpers for `managers.tools`.

This package loads tool metadata from JSON files and resolves the matching
Python handler functions used by the bot.
"""

import importlib
import json
import time
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger()

DEFAULT_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "tools"


class ToolsLoader:
    def __init__(self, tools_dir: Path | str = DEFAULT_TOOLS_DIR):
        self.tools_dir = Path(tools_dir)
        self.tools_metadata: list[dict[str, Any]] = []
        self.tools_handlers: dict[str, Any] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        start = time.perf_counter()
        loaded: list[str] = []
        failed: list[str] = []
        if not self.tools_dir.exists():
            logger.warning("Tools directory not found: %s", self.tools_dir)
            return

        for path in sorted(self.tools_dir.glob("*.json")):
            tool_name = path.stem

            try:
                with path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)

                name_field = raw.get("name", tool_name) if isinstance(raw, dict) else tool_name
                description = raw.get("description", "") if isinstance(raw, dict) else ""
                parameters = raw.get("inputSchema") or raw.get("parameters") or {} if isinstance(raw, dict) else {}
                self.tools_metadata.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name_field,
                            "description": description,
                            "parameters": parameters,
                        },
                    }
                )

                module = importlib.import_module(f"managers.tools.{tool_name}")
                handler = getattr(module, tool_name)
                self.tools_handlers[tool_name] = handler
                loaded.append(tool_name)
                logger.debug("Loaded tool: %s", tool_name)
            except Exception:
                failed.append(tool_name)
                logger.exception("Failed to load tool %s", tool_name)

        elapsed = time.perf_counter() - start
        logger.info(
            "ToolsLoader: loaded %d tools, failed %d, in %.2fs",
            len(loaded),
            len(failed),
            elapsed,
        )
        if loaded:
            logger.debug("Tools loaded: %s", ", ".join(loaded))
        if failed:
            logger.debug("Tools failed: %s", ", ".join(failed))

    async def call_tool(self, tool_name: str, args: dict) -> str:
        if tool_name not in self.tools_handlers:
            return f"Unknown tool: {tool_name}"

        try:
            handler = self.tools_handlers[tool_name]
            result = await handler(**args)
            return str(result)
        except Exception as exc:
            logger.error("Error calling tool %s: %s", tool_name, exc)
            return f"Error: {exc!s}"


_TOOLS_LOADER_INSTANCE: ToolsLoader | None = None


def get_tools_loader(tools_dir: Path | str = DEFAULT_TOOLS_DIR) -> ToolsLoader:
    global _TOOLS_LOADER_INSTANCE
    if _TOOLS_LOADER_INSTANCE is None:
        _TOOLS_LOADER_INSTANCE = ToolsLoader(tools_dir)
    return _TOOLS_LOADER_INSTANCE
