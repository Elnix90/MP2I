"""AI answering helpers.

Generates answers using an OpenAI-compatible API and
manages the list of channels the bot is allowed to answer in.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from starlette.responses import StreamingResponse

from core.config import cfg
from utils.logger import get_logger

logger = get_logger()

AI_STATE_PATH = Path("data") / "ai_state.json"


def _get_auth_header(headers: Dict[str, str]) -> str:
    auth = headers.get("authorization", "")
    if auth:
        return auth
    if cfg.AI_API_KEY:
        return f"Bearer {cfg.AI_API_KEY}"
    return ""


def load_allowed_channels() -> list[int]:
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


def _extract_content(message: dict) -> str:
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


def _parse_stream_chunk(line: str) -> str:
    if not line.startswith("data: ") or line == "data: [DONE]":
        return ""
    try:
        return json.loads(line[6:])["choices"][0]["delta"].get("content", "")
    except (json.JSONDecodeError, KeyError):
        return ""


async def generate_answer(
    messages: list[dict[str, str]],
    request: Optional[Any] = None,
    *,
    timeout: int = 120,
) -> str:
    if request is not None:
        headers = dict(request.headers)
        body: Dict[str, Any] = await request.json()
    else:
        headers = {}
        body = {}

    auth = _get_auth_header(headers)
    headers = {
        "Content-Type": "application/json",
    }
    if auth:
        headers["Authorization"] = auth

    payload = {
        "model": cfg.AI_MODEL,
        "messages": messages,
        "stream": False,
    }

    print(f"Requesting answer from OpenCode API: {messages}")
    print(f"Request payload: {payload}")
    print(f"Request headers: {headers}")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.post(
                cfg.AI_API_URL,
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = _extract_content(data["choices"][0]["message"]).strip()
        if not content:
            logger.warning("OpenCode API returned an empty answer")
        else:
            logger.debug(f"Anwser generated: for prompt: {messages}")
        return content
    except Exception:
        logger.exception("OpenCode API error")
        return "Désolé, une erreur m'a empêché de répondre (t'appelleras le prof si ça continue)."


async def chat_completions(request: Optional[Any] = None):
    if request is not None:
        headers = dict(request.headers)
        body: Dict[str, Any] = await request.json()
    else:
        headers = {}
        body = {}

    auth = _get_auth_header(headers)
    if auth:
        headers["Authorization"] = auth

    async def stream_generator():
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            async with client.stream(
                "POST",
                cfg.AI_API_URL,
                headers=headers,
                json=body,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])
                            content = data["choices"][0]["delta"].get("content", "")
                            if content:
                                yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
                        except (json.JSONDecodeError, KeyError):
                            continue
                yield "data: [DONE]\n\n"

    if body.get("stream", False):
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                cfg.AI_API_URL,
                headers=upstream_headers,
                json=body,
            )
            return resp.json()
