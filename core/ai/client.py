"""LLM client with manual model fallback and native tool calling.

Uses the ``openai`` AsyncOpenAI client against the configured OpenAI-compatible
endpoint. Models listed in ``cfg.AI_MODELS`` are tried in order: on timeout,
HTTP error or empty answer the next model takes over. No LiteLLM.

When ``tools`` are provided the client runs a native tool-calling loop: the
model emits function calls, they are executed in parallel, results are fed
back, and a final answer is produced. Streaming applies to the final round.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from core.ai.tools import handle_tool_call, parse_tool_arguments
from core.config import cfg
from db.settings_store import get_setting
from utils.logger import get_logger

logger = get_logger()

REQUEST_TIMEOUT = 60.0
MAX_RETRIES = 1
MAX_TOOL_ITERATIONS = 6
DEFAULT_MAX_CONTEXT_CHARS = 128000


@dataclass
class Answer:
    content: str = ""
    model: str | None = None
    response_time: float | None = None
    error: str | None = None
    error_detail: str | None = None


def _model_priority() -> list[str]:
    models = list(cfg.AI_MODELS)
    if not models:
        return []
    # runtime override (persisted by /model) wins as primary
    override = get_setting("ai.model")
    if isinstance(override, str) and override:
        models = [override] + [m for m in models if m != override]
    elif cfg.AI_MODEL and cfg.AI_MODEL not in models:
        models.insert(0, cfg.AI_MODEL)
    return models


def _build_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=cfg.AI_API_URL,
        api_key=cfg.AI_API_KEY,
        timeout=REQUEST_TIMEOUT,
        max_retries=MAX_RETRIES,
    )


def _messages_char_size(msgs: list) -> int:
    try:
        return len(json.dumps(msgs, ensure_ascii=False))
    except Exception:
        return sum(len(str(m)) for m in msgs)


def _truncate_messages(msgs: list, max_chars: int = DEFAULT_MAX_CONTEXT_CHARS) -> list:
    if not isinstance(msgs, list):
        return msgs
    size = _messages_char_size(msgs)
    if size <= max_chars or not any(m.get("role") != "system" for m in msgs):
        return msgs
    copy = list(msgs)
    removed = 0
    while _messages_char_size(copy) > max_chars and any(m.get("role") != "system" for m in copy):
        for idx, m in enumerate(copy):
            if m.get("role") != "system":
                del copy[idx]
                removed += 1
                break
    logger.info(
        "Truncated messages: removed %d messages; final size %d chars",
        removed,
        _messages_char_size(copy),
    )
    return copy


def _payload_kwargs(tools: list | None) -> dict:
    kwargs: dict = {}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return kwargs


_ATEM_BLOCK = re.compile(
    r"<atem:function_calls\b.*?</atem:function_calls>",
    re.DOTALL | re.IGNORECASE,
)
_ATEM_INVOKE = re.compile(r"<atem:invoke\b.*?</atem:invoke>", re.DOTALL | re.IGNORECASE)
_ATEM_TO_TOKEN = re.compile(r"to=\w+<\|[^|]*\|>")
_ATEM_MARKER = re.compile(r"<\|[^|]*\|>")


def strip_tool_artifacts(text: str) -> str:
    if not text:
        return text
    cleaned = _ATEM_BLOCK.sub(" ", text)
    cleaned = _ATEM_INVOKE.sub(" ", cleaned)
    cleaned = _ATEM_TO_TOKEN.sub(" ", cleaned)
    cleaned = _ATEM_MARKER.sub(" ", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    return cleaned.strip()


async def _run_round(
    client: AsyncOpenAI,
    model: str,
    messages: list,
    tools: list | None,
) -> tuple[object | None, list, str | None]:
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            **_payload_kwargs(tools),
        )
        message = resp.choices[0].message
        return message, list(getattr(message, "tool_calls", None) or []), None
    except Exception as exc:
        logger.warning("Round failed for model %s", model, exc_info=True)
        return None, [], str(exc)


def _assistant_tool_message(message: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "role": "assistant",
        "content": strip_tool_artifacts(getattr(message, "content", None) or ""),
    }
    base["tool_calls"] = [
        {
            "id": tc.id,
            "type": getattr(tc, "type", "function"),
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in getattr(message, "tool_calls", [])
    ]
    return base


async def _execute_tool_calls(tool_calls: list) -> list[dict]:
    async def _run(tool_call) -> dict:
        arguments = parse_tool_arguments(tool_call.function.arguments)
        logger.info(
            "Tool call: %s args=%s",
            tool_call.function.name,
            {k: str(v)[:80] for k, v in arguments.items()},
        )
        result = await handle_tool_call(tool_call.function.name, arguments)
        return {
            "tool_call_id": tool_call.id,
            "role": "tool",
            "name": tool_call.function.name,
            "content": result,
        }

    return await asyncio.gather(*(_run(tc) for tc in tool_calls))


async def generate_answer(
    messages: list,
    *,
    stream: bool = False,
    tools: list | None = None,
) -> Answer | AsyncIterator[Any]:
    models = _model_priority()
    if not models:
        return Answer(
            content="Désolé, aucune configuration d'IA disponible.",
            error="no_models",
        )
    if not cfg.AI_API_KEY or not cfg.AI_API_URL:
        return Answer(
            content="IA non configurée (clé ou URL manquante).",
            error="misconfigured",
        )

    client = _build_client()
    round_messages = _truncate_messages(messages)
    last_error: str | None = None

    for _ in range(MAX_TOOL_ITERATIONS):
        round_outcome = None
        for model in models:
            message, tool_calls, err = await _run_round(client, model, round_messages, tools)
            if message is not None:
                round_outcome = (model, message, tool_calls)
                break
            last_error = err or last_error
        if round_outcome is None:
            break  # every model failed this round

        used_model, message, tool_calls = round_outcome

        if tool_calls and tools:
            round_messages.append(_assistant_tool_message(message))
            round_messages.extend(await _execute_tool_calls(tool_calls))
            round_messages = _truncate_messages(round_messages)
            continue

        content = strip_tool_artifacts(getattr(message, "content", None) or "")
        if stream:
            final = await _stream_final(client, used_model, round_messages)
            if final is not None:
                return final
        else:
            return Answer(content=content, model=used_model)

    # Tool loop exhausted without a plain-text answer, or all models failed:
    # run one final synthesis pass without tools before giving up.
    synthesis = await _synthesize(client, models, round_messages, stream=stream)
    if synthesis is not None:
        return synthesis

    return Answer(
        content="Toutes mes sources de haine sont saturées (ou une erreur est survenue).",
        error="all_failed",
        error_detail=last_error,
    )


async def _stream_final(client: AsyncOpenAI, model: str, messages: list) -> AsyncIterator[Any] | None:
    try:
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
    except Exception:
        logger.warning("Stream failed for model %s", model, exc_info=True)
        return None


async def _synthesize(
    client: AsyncOpenAI,
    models: list,
    messages: list,
    *,
    stream: bool,
) -> Answer | AsyncIterator[Any] | None:
    stream_result = None
    for model in models:
        try:
            if stream:
                final = await _stream_final(client, model, messages)
                if final is not None:
                    stream_result = final
                    continue
            else:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                )
                content = resp.choices[0].message.content
                if content:
                    return Answer(
                        content=strip_tool_artifacts(content),
                        model=model,
                    )
        except Exception:
            logger.warning("Synthesis failed for model %s", model, exc_info=True)

    if stream_result is not None:
        return stream_result
    return None
