"""AI layer for the MP2I bot.

Backward-compatible facade: the old ``core.ai`` module exposed
``generate_answer(message) -> str`` and ``is_allowed_channel``. Keep those
signatures working while the richer client lives in ``.client``.
"""

from core.ai.channels import is_allowed_channel
from core.ai.client import (
    Answer,
    generate_answer as _generate_answer,
)
from core.config import cfg
from utils.logger import get_logger

__all__ = [
    "Answer",
    "generate_answer",
    "is_allowed_channel",
]

logger = get_logger()


async def generate_answer(message: str) -> str:
    messages = [
        {"role": "system", "content": cfg.AI_SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    answer = await _generate_answer(messages, stream=False)
    return (answer.content or "No answer") if isinstance(answer, Answer) else "No answer"
