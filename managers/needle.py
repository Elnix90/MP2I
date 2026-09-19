"""Local tool routing with Cactus Needle.

When ``needle_tool_calling`` is enabled in ``config/ai_config.json5``, every
user request is routed through the local Needle engine *before* hitting the
cloud model. Needle returns only the tools that can serve the request; the
cloud model then receives that subset instead of the full catalogue.

Contract:
- A request no tool can serve yields an empty call list, so the cloud model
  gets no tools at all (pure chat).
- ``suppressed_calls`` (below the confidence floor) are logged, not exposed.
- Any failure degrades to the full, unfiltered tool list.
- The package stays optional: imported lazily, so the bot boots and runs
  without it installed.
"""

import asyncio
import copy
import os
import threading
from dataclasses import dataclass, field
from typing import Any

os.environ.setdefault("NEEDLE_TELEMETRY", "0")

from core.config import cfg
from utils.logger import get_logger

logger = get_logger()


@dataclass
class ToolSelection:
    tools: list[dict] = field(default_factory=list)
    confidence: float | None = None
    reasoning: str = ""
    suppressed: list[str] = field(default_factory=list)
    routed: bool = False


class NeedleRouter:
    SYSTEM_FACTS = "locale: fr-FR; device: discord-bot"

    def __init__(self) -> None:
        self._agent: Any | None = None
        self._fingerprint: tuple[str, ...] | None = None
        self._lock = threading.Lock()
        self._unavailable_logged = False

    @staticmethod
    def _fingerprint_of(tools_meta: list[dict]) -> tuple[str, ...]:
        return tuple(sorted(t["function"]["name"] for t in tools_meta))

    def _build_agent(self, tools_meta: list[dict]) -> Any:
        import needle

        return needle.Needle(tools=self._tools_with_triggers(tools_meta), system=self.SYSTEM_FACTS)

    def _tools_with_triggers(self, tools_meta: list[dict]) -> list[dict]:
        """Merge tool ``triggers`` from the native loader into the Needle schemas.

        The cloud-facing metadata must stay free of ``triggers`` (OpenAI rejects
        unknown keys), so they only ride along into the local Needle toolset.
        """
        try:
            from managers.tools import get_tools_loader

            triggers = get_tools_loader().tools_triggers
        except Exception:
            triggers = {}

        merged = []
        for tool in tools_meta:
            name = tool.get("function", {}).get("name")
            extra = triggers.get(name)
            if not extra:
                merged.append(tool)
                continue
            tool = copy.deepcopy(tool)
            tool["function"]["triggers"] = extra
            merged.append(tool)
        return merged

    def _sync_select(self, user_text: str, tools_meta: list[dict]) -> ToolSelection:
        fingerprint = self._fingerprint_of(tools_meta)
        with self._lock:
            agent = self._agent
            if agent is None or fingerprint != self._fingerprint:
                agent = self._build_agent(tools_meta)
                self._agent = agent
                self._fingerprint = fingerprint
            out = agent.complete(user_text)
            agent.reset()

        if not isinstance(out, dict):
            raise TypeError(f"unexpected Needle response: {type(out).__name__}")

        by_name = {t["function"]["name"]: t for t in tools_meta}
        kept = []
        unknown = []
        for call in out.get("function_calls") or []:
            name = call.get("name")
            if name in by_name:
                kept.append(by_name[name])
            else:
                unknown.append(name)

        if unknown:
            logger.warning("Needle returned unknown tool names: %s", unknown)

        suppressed = [c.get("name") for c in out.get("suppressed_calls") or [] if c.get("name")]

        return ToolSelection(
            tools=kept,
            confidence=out.get("confidence"),
            reasoning=out.get("reasoning") or "",
            suppressed=suppressed,
            routed=True,
        )

    def _log_unavailable(self, exc: Exception) -> None:
        if not self._unavailable_logged:
            self._unavailable_logged = True
            logger.warning(
                "Needle tool filtering unavailable (%s) - sending the full tool list. Fix: pip install 'cactus-needle' and enable needle_tool_calling.",
                exc,
            )

    async def select_tools(self, user_text: str, tools_meta: list[dict]) -> ToolSelection:
        if not self.enabled or not tools_meta:
            return ToolSelection(tools=tools_meta)

        try:
            import needle  # noqa: F401
        except ImportError as exc:
            self._log_unavailable(exc)
            return ToolSelection(tools=tools_meta)

        try:
            return await asyncio.to_thread(self._sync_select, user_text, tools_meta)
        except Exception as exc:
            self._log_unavailable(exc)
            return ToolSelection(tools=tools_meta)

    @property
    def enabled(self) -> bool:
        return bool(cfg.AI_NEEDLE_TOOL_CALLING)


needle_router = NeedleRouter()
