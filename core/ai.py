"""AI answering helpers.

Generates answers using an OpenAI-compatible API and
manages the list of channels the bot is allowed to answer in.
"""

import json
from pathlib import Path

from openai import AsyncOpenAI

from core.config import cfg
from utils.logger import get_logger

logger = get_logger()

AI_STATE_PATH = Path("data") / "ai_state.json"


def load_allowed_channels() -> list[int]:
    if not AI_STATE_PATH.exists():
        return list(cfg.AI_ALLOWED_CHANNELS)
    try:
        with open(AI_STATE_PATH, encoding="utf-8") as f:
            payload = json.load(f)
        return [int(c) for c in payload.get("allowed_channels", [])]
    except Exception:
        logger.warning("Failed to read allowed AI channels", exc_info=True)
        return list(cfg.AI_ALLOWED_CHANNELS)


def save_allowed_channels(channels: list[int]) -> None:
    try:
        AI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(AI_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"allowed_channels": [int(c) for c in channels]}, f, indent=2)
    except Exception:
        logger.warning("Failed to write allowed AI channels", exc_info=True)


def is_allowed_channel(channel_id: int | None) -> bool:
    if channel_id is None:
        return False
    return channel_id in load_allowed_channels()


_CLIENT = AsyncOpenAI(
    base_url=cfg.AI_API_URL,
    api_key=cfg.AI_API_KEY,
    timeout=60.0,
    max_retries=1,
)


async def generate_answer(message: str) -> str:
    try:
        response = await _CLIENT.chat.completions.create(
            model=cfg.AI_MODEL,
            messages=[
                {"role": "system", "content": cfg.AI_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
        )

        answer = response.choices[0].message.content

        if answer is None:
            logger.warning("AI API returned an empty answer")
        else:
            logger.debug(f"Anwser generated: for prompt: {message}")
        return answer or "No answer"
    except Exception:
        logger.exception("AI API error")
        return "Désolé, une erreur m'a empêché de répondre (t'appelleras le prof si ça continue)."
