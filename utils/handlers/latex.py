"""Helpers for detecting and rendering LaTeX content.

Rendering is done locally by the ``mp2i-render`` binary (a Rust wrapper around
the RaTeX engine, ``renderer/`` in this repo). The formula is piped on stdin
and a PNG is read back on stdout. A small cache avoids re-rendering the same
formula.
"""

import asyncio
import io
import os
import re
from pathlib import Path

from utils.logger import get_logger

logger = get_logger()

RENDERER_BIN_DEFAULT = Path(__file__).resolve().parent.parent.parent / "renderer" / "target" / "release" / "mp2i-render"

# binary used to render LaTeX -> PNG (override via LATEX_RENDERER_BIN)
RENDERER_BIN = os.getenv("LATEX_RENDERER_BIN", "").strip() or str(RENDERER_BIN_DEFAULT)
# resolution multiplier kept in sync with the old cairosvg `scale=2`
RENDERER_SCALE = float(os.getenv("LATEX_RENDERER_SCALE", "2"))
RENDER_TIMEOUT = 10  # seconds

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

_PNG_MAGIC = b"\x89PNG"


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


def renderer_available() -> bool:
    path = Path(RENDERER_BIN)
    return path.is_file() and os.access(path, os.X_OK)


async def render_latex_to_png(latex: str) -> tuple[io.BytesIO | None, str | None]:
    """Render a formula with the local Rust renderer.

    Returns ``(png_bytes, None)`` on success or ``(None, error_message)``.
    """
    proc = await asyncio.create_subprocess_exec(
        RENDERER_BIN,
        "--scale",
        f"{RENDERER_SCALE:g}",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(latex.encode("utf-8")),
        timeout=RENDER_TIMEOUT,
    )
    if proc.returncode != 0 or not stdout.startswith(_PNG_MAGIC):
        err = stderr.decode("utf-8", errors="replace").strip() or f"exit status {proc.returncode}"
        return None, err
    return io.BytesIO(stdout), None


async def convert_latex_to_png(latex: str) -> tuple[io.BytesIO | str, bool]:
    cleaned = latex.strip()
    if cleaned.startswith(r"\(") and cleaned.endswith(r"\)"):
        cleaned = cleaned[2:-2]
    cleaned = cleaned.strip("$")

    cached = _cached(cleaned)
    if cached is not None:
        cached.seek(0)
        return cached, True

    try:
        png, error = await render_latex_to_png(cleaned)
        if png is None:
            return f"```\n{latex}\n``` ({error})", False
        return _store(cleaned, png), True
    except Exception as exc:
        logger.error("LaTeX conversion failed: %s", exc)
        return f"```\n{latex}\n```", False


def detect_latex(text: str) -> list[str]:
    return LATEX_PATTERN.findall(text)
