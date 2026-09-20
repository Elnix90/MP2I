"""Helpers for detecting and rendering LaTeX content.

Rendering uses ``math.vercel.app`` (SVG) converted to PNG with cairosvg.
Requests carry browser-like headers and retry once on rate limits to dodge
aggressive throttling; a small cache avoids re-rendering the same formula.
"""

import asyncio
import io
import re
import time
import urllib.parse

import aiohttp
from aiohttp.client import ClientTimeout

from utils.logger import get_logger

try:
    import cairosvg
except ImportError:
    cairosvg = None

logger = get_logger()

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "image/svg+xml,image/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RATE_LIMIT_STATUS = 429
REMOTE_MIN_INTERVAL = 0.4  # seconds between remote render requests

LATEX_TO_EMOJI = {
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\delta": "δ",
    r"\epsilon": "ε",
    r"\zeta": "ζ",
    r"\eta": "η",
    r"\theta": "θ",
    r"\iota": "ι",
    r"\kappa": "κ",
    r"\lambda": "λ",
    r"\mu": "μ",
    r"\nu": "ν",
    r"\xi": "ξ",
    r"\pi": "π",
    r"\rho": "ρ",
    r"\sigma": "σ",
    r"\tau": "τ",
    r"\upsilon": "υ",
    r"\phi": "φ",
    r"\chi": "χ",
    r"\psi": "ψ",
    r"\omega": "ω",
    r"\Gamma": "Γ",
    r"\Delta": "Δ",
    r"\Theta": "Θ",
    r"\Lambda": "Λ",
    r"\Xi": "Ξ",
    r"\Pi": "Π",
    r"\Sigma": "Σ",
    r"\Upsilon": "Υ",
    r"\Phi": "Φ",
    r"\Psi": "Ψ",
    r"\Omega": "Ω",
    r"\sum": "∑",
    r"\prod": "∏",
    r"\int": "∫",
    r"\infty": "∞",
    r"\neq": "≠",
    r"\leq": "≤",
    r"\geq": "≥",
    r"\approx": "≈",
    r"\times": "×",
    r"\div": "÷",
}

LATEX_PATTERN = re.compile(
    r"```(?:latex|tex)[\s\S]*?```|"
    r"\$\$[\s\S]*?\$\$|"
    r"\\\[[\s\S]*?\\\]|"
    r"\\\([\s\S]*?\\\)|"
    r"\$[^$]+?\$",
)

# simple render cache keyed by cleaned latex -> BytesIO
_LATEX_CACHE: dict[str, io.BytesIO] = {}
_LATEX_CACHE_MAX = 128
_last_remote_request = 0.0


def _cache_key(latex: str) -> str:
    return latex.strip()


def _cached(latex: str) -> io.BytesIO | None:
    return _LATEX_CACHE.get(_cache_key(latex))


def _store(latex: str, buffer: io.BytesIO) -> io.BytesIO:
    if len(_LATEX_CACHE) >= _LATEX_CACHE_MAX:
        oldest_key = next(iter(_LATEX_CACHE))
        del _LATEX_CACHE[oldest_key]
    _LATEX_CACHE[_cache_key(latex)] = buffer
    return buffer


async def latex_to_svg(formula: str) -> bytes:
    global _last_remote_request
    encoded = urllib.parse.quote(formula, safe="")
    url = f"https://math.vercel.app?color=white&from={encoded}.svg"

    for attempt in range(2):
        # throttle: keep a minimum gap between remote requests
        elapsed = time.monotonic() - _last_remote_request
        if elapsed < REMOTE_MIN_INTERVAL:
            await asyncio.sleep(REMOTE_MIN_INTERVAL - elapsed)
        _last_remote_request = time.monotonic()

        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    url,
                    headers=BROWSER_HEADERS,
                    timeout=ClientTimeout(10),
                )
            if response.status == RATE_LIMIT_STATUS:
                logger.warning(
                    "math.vercel.app rate-limited (attempt %d), backing off",
                    attempt + 1,
                )
                await asyncio.sleep(1.0 + attempt)
                continue
            return await response.read()
        except aiohttp.ClientError as exc:
            if attempt == 0:
                logger.warning("math.vercel.app request failed, retrying: %s", exc)
                await asyncio.sleep(1.0)
                continue
            raise

    # both attempts rate-limited
    raise RuntimeError("math.vercel.app rate limited")


async def convert_latex_to_png(latex: str) -> tuple[io.BytesIO | str, bool]:
    cleaned = latex.strip()
    if cleaned.startswith(r"\(") and cleaned.endswith(r"\)"):
        cleaned = cleaned[2:-2]
    cleaned = cleaned.strip("$")

    cached = _cached(cleaned)
    if cached is not None:
        cached.seek(0)
        return cached, True

    if not cairosvg:
        return f"```\n{latex}\n``` (cairosvg missing)", False

    try:
        svg_bytes = await latex_to_svg(cleaned)
        png_bytes = cairosvg.svg2png(bytestring=svg_bytes, scale=2)
        if png_bytes is None:
            return f"```\n{latex}\n``` (conversion failed)", False
        return _store(cleaned, io.BytesIO(png_bytes)), True
    except Exception as exc:
        logger.error("LaTeX conversion failed: %s", exc)
        return f"```\n{latex}\n```", False


def detect_latex(text: str) -> list[str]:
    return LATEX_PATTERN.findall(text)
