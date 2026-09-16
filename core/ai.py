"""AI answering helpers.

Generates answers using the OpenCode free API (no auth required) and
manages the list of channels the bot is allowed to answer in.
"""

import json
import uuid
from pathlib import Path

import aiohttp

from core.config import cfg
from utils.logger import get_logger

logger = get_logger()

AI_STATE_PATH = Path("data") / "ai_state.json"

_SESSION_ID = f"ses_{uuid.uuid4()}"
_BASE_HEADERS = {
    "User-Agent": "opencode/1.15.0 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.13",
    "x-opencode-client": "cli",
    "x-opencode-project": "global",
}


def load_allowed_channels() -> list[int]:
    """Return the persisted list of channel IDs where the bot may answer.

    The state file, once written by an admin command, becomes the source
    of truth. Before any admin command is used, the config value applies.
    """
    if not AI_STATE_PATH.exists():
        return list(cfg.AI_ALLOWED_CHANNELS)
    try:
        with open(AI_STATE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return [int(c) for c in payload.get("allowed_channels", [])]
    except Exception:
        logger.warning("Failed to read allowed AI channels", exc_info=True)
        return list(cfg.AI_ALLOWED_CHANNELS)


def save_allowed_channels(channels: list[int]) -> None:
    """Persist the list of channel IDs the bot may answer in."""
    try:
        AI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AI_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"allowed_channels": [int(c) for c in channels]}, f, indent=2)
    except Exception:
        logger.warning("Failed to write allowed AI channels", exc_info=True)


def is_allowed_channel(channel_id: int | None) -> bool:
    """Return True when the bot is allowed to answer in the given channel."""
    if channel_id is None:
        return False
    return channel_id in load_allowed_channels()


def _extract_content(message: dict) -> str:
    """Extract the assistant text from an OpenAI-style chat message."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(part.get("text", ""))
        return "".join(parts)
    return ""


async def generate_answer(messages: list[dict[str, str]], *, timeout: int = 120) -> str:
    """Generate an answer from `messages` using the OpenCode free model.

    The free tier does not require a real API key: the "public" key plus
    the session/request headers normally sent by the opencode CLI suffice.
    """
    payload = {
        "model": cfg.AI_MODEL,
        "messages": messages,
        "stream": False,
    }
    headers = {
        **_BASE_HEADERS,
        "Authorization": "Bearer public",
        "Content-Type": "application/json",
        "x-opencode-request": f"msg_{uuid.uuid4()}",
        "x-opencode-session": _SESSION_ID,
    }
    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                cfg.AI_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp,
        ):
            resp.raise_for_status()
            data = await resp.json()

        content = _extract_content(data["choices"][0]["message"]).strip()
        if not content:
            logger.warning("OpenCode API returned an empty answer")
        else:
            logger.debug(f"Anwser generated: for prompt: {messages}")
        return content
    except Exception:
        logger.exception("OpenCode API error")
        return "Désolé, une erreur m'a empêché de répondre (t'appelleras le prof si ça continue)."
