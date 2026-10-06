"""Model selection: default to the free and healthy models.

``GET {AI_API_URL}/models`` describes every model the endpoint serves, with a
``pricing`` dict, an optional ``agent`` flag and a ``health.status``. The
catalogue is refreshed at startup and every ``REFRESH_INTERVAL`` seconds so a
model that degrades drops out of the rotation without a restart.

``is_free`` mirrors the dashboard's ``access:free`` filter
(enter.pollinations.ai/models): an agent or router bills whatever it delegates
to, so an empty ``pricing`` dict does not make it free.

A failed fetch keeps the previous catalogue. With no catalogue at all the
rotation is empty and ``generate_answer`` answers ``no_models``: there is no
static fallback list anymore (``ai_config.json5`` carries no ``models``).
"""

from __future__ import annotations

import asyncio
import time

import aiohttp

from core.config import cfg
from db.settings_store import get_setting
from utils.logger import get_logger

logger = get_logger()

REFRESH_INTERVAL = 300.0
REQUEST_TIMEOUT = 15.0
MAX_MODELS = 6
# Dashboard's ``status:reliable`` threshold: ``success_rate > 80``.
RELIABLE_THRESHOLD = 80

_catalog: list[str] = []
_refreshed_at = 0.0
_lock = asyncio.Lock()


_PROMPT_KEYS = (
    "promptTextTokens",
    "promptCachedTokens",
    "promptCacheWriteTokens",
    "promptAudioTokens",
    "promptAudioSeconds",
    "promptImageTokens",
    "promptVideoTokens",
)
_COMPLETION_KEYS = (
    "completionTextTokens",
    "completionReasoningTokens",
    "completionAudioTokens",
    "completionAudioSeconds",
    "completionImageTokens",
    "completionVideoSeconds",
    "completionVideoTokens",
)


def _priced_total(pricing: dict, keys: tuple[str, ...]) -> float:
    """Sum of the positive token rates: anything above zero costs money."""
    total = 0.0
    for key in keys:
        raw = pricing.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            total += value
    return total


def is_free(model: dict) -> bool:
    """Same rule as the dashboard ``access:free`` token.

    ``!agent && pricing != None && no input price && no output price &&
    no positive pricing_adjustments && !paid_only``. Agents and routers are
    never free: their price is whatever the model they delegate to charges
    (``polli``, ``floret``, ``frugal``, the routers, ...).
    """
    if model.get("agent") or model.get("paid_only"):
        return False
    pricing = model.get("pricing")
    if pricing is None:
        return False
    if _priced_total(pricing, _PROMPT_KEYS) or _priced_total(pricing, _COMPLETION_KEYS):
        return False
    for adjustment in model.get("pricing_adjustments") or []:
        try:
            if float(adjustment.get("price") or 0) > 0:
                return False
        except (TypeError, ValueError):
            continue
    return True


def is_healthy(model: dict) -> bool:
    """Healthy, or close enough: the dashboard's ``status:healthy`` OR ``status:reliable``.

    ``reliable`` keeps a ``degraded`` model as long as it still answers
    ``success_rate > 80`` — otherwise the eligible list drops to a handful of
    models whenever a few degrade at the same time.
    """
    health = model.get("health") or {}
    if health.get("status") == "healthy":
        return True
    rate = health.get("success_rate")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return False
    return rate > RELIABLE_THRESHOLD


def is_chat(model: dict) -> bool:
    """Skip image/audio/video/embedding models: we only answer on chat completions."""
    endpoints = model.get("supported_endpoints") or []
    return model.get("category") == "text" and "/v1/chat/completions" in endpoints


def select(models: list[dict]) -> list[str]:
    """Free + healthy chat models, most trustworthy first."""
    selected = [model for model in models if is_free(model) and is_healthy(model) and is_chat(model)]
    selected.sort(
        key=lambda model: (
            not bool(model.get("tools")),  # tool calling first: the bot runs tools
            -(model["health"].get("success_rate") or 0),
            -(model["health"].get("requests") or 0),
            str(model.get("id")),
        )
    )
    return [str(model["id"]) for model in selected]


def candidates() -> list[str]:
    """Current catalogue (empty until the first successful refresh)."""
    return list(_catalog)


def default_model() -> str:
    """The model the bot uses unless a manual ``/model`` override exists."""
    override = get_setting("ai.model")
    if isinstance(override, str) and override:
        return override
    return _catalog[0] if _catalog else (cfg.AI_MODELS[0] if cfg.AI_MODELS else "")


def priority(fallback: list[str] | None = None) -> list[str]:
    """Model rotation: manual override, free+healthy catalogue, then configured fallbacks.

    The catalogue only ever holds free and healthy models, so it comes before
    the statically configured list (which cannot be verified and is often stale).
    """
    ordered: list[str] = []

    def add(model: str) -> None:
        if model and model not in ordered:
            ordered.append(model)

    override = get_setting("ai.model")
    if isinstance(override, str) and override:
        add(override)

    for model in _catalog:
        add(model)
    for model in cfg.AI_MODELS if fallback is None else fallback:
        add(model)

    return ordered[:MAX_MODELS]


async def refresh(*, force: bool = False) -> list[str]:
    """Fetch the model catalogue; on failure keep the last known one."""
    global _catalog, _refreshed_at

    if not force and _catalog and time.monotonic() - _refreshed_at < REFRESH_INTERVAL:
        return list(_catalog)

    async with _lock:
        if not force and _catalog and time.monotonic() - _refreshed_at < REFRESH_INTERVAL:
            return list(_catalog)

        url = f"{cfg.AI_API_URL.rstrip('/')}/models"
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response,
            ):
                response.raise_for_status()
                payload = await response.json()
        except Exception as exc:
            logger.warning("Model catalogue unavailable (%s), keeping %d model(s)", exc, len(_catalog))
            return list(_catalog)

        models = payload.get("data") if isinstance(payload, dict) else payload
        catalog = select(models if isinstance(models, list) else [])
        if not catalog:
            logger.warning("No free and healthy chat model reported by %s", url)
            return list(_catalog)

        _catalog = catalog
        _refreshed_at = time.monotonic()
        logger.info("Model catalogue: %d free+healthy model(s), default is %s", len(catalog), catalog[0])

        override = get_setting("ai.model")
        if not (isinstance(override, str) and override):
            cfg.AI_MODEL = catalog[0]
        return list(_catalog)
