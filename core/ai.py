"""AI answering helpers.

Generates answers using an OpenAI-compatible API and
manages the list of channels the bot is allowed to answer in.
"""

from openai import AsyncOpenAI

from core.config import cfg
from db.settings_store import get_setting, set_setting
from utils.logger import get_logger

logger = get_logger()


def load_allowed_channels() -> list[int]:
    stored = get_setting("ai.allowed_channels")
    if stored is None:
        return list(cfg.AI_ALLOWED_CHANNELS)
    if not isinstance(stored, list):
        logger.warning("Invalid allowed AI channels in store, using config default")
        return list(cfg.AI_ALLOWED_CHANNELS)
    try:
        return [int(c) for c in stored]
    except (TypeError, ValueError):
        logger.warning("Invalid allowed AI channels in store, using config default")
        return list(cfg.AI_ALLOWED_CHANNELS)


def save_allowed_channels(channels: list[int]) -> None:
    set_setting("ai.allowed_channels", [int(c) for c in channels])


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
