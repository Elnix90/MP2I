"""System prompt assembly for the AI layer.

Combines the base personality prompt (``config/prompts/system.md``) with
optional server context and tool-use instructions.
"""

from core.config import cfg


def build_system_prompt(
    server_context: str | None = None,
    *,
    include_tools: bool = True,
) -> str:
    parts = [cfg.AI_SYSTEM_PROMPT]
    if server_context:
        parts.append(server_context)
    return "\n\n".join(parts)
