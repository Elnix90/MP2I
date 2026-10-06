"""Local text embeddings for the memory system (multilingual MiniLM over ONNX Runtime).

Computes embeddings in-process with ``fastembed``, replacing the cloud Pollinations
endpoint: a turn costs ~20-130 ms of CPU instead of a network round trip, works
offline and leaves room for batching.

``fastembed`` honours ``model_max_length`` from the model's ``tokenizer_config.json``,
which is 128 for this checkpoint: without the override below, everything past ~600
characters would be silently dropped instead of embedded.

Its default cache is ``$TMPDIR/fastembed_cache``, which a reboot wipes; the model
is pinned to a persistent one instead.
"""

from __future__ import annotations

import asyncio
import math
import os
import threading
import time
from pathlib import Path

from fastembed import TextEmbedding

from utils.logger import get_logger

logger = get_logger()

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384
MAX_TOKENS = 512
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "fastembed"

_model: TextEmbedding | None = None
_model_lock = threading.Lock()


def _load() -> TextEmbedding:
    """Load the model once, downloading it into ``CACHE_DIR`` on first use."""
    global _model
    if _model is None:
        logger.info("Loading local embedding model %s…", MODEL_NAME)
        start = time.perf_counter()
        model = TextEmbedding(MODEL_NAME, cache_dir=os.getenv("FASTEMBED_CACHE_PATH", str(CACHE_DIR)))
        _raise_truncation(model)
        _model = model
        logger.info("Embedding model ready in %.1fs (%d dims)", time.perf_counter() - start, DIM)
    return _model


def _raise_truncation(model: TextEmbedding) -> None:
    """Embed the whole message, not just the first ~128 tokens of it."""
    tokenizer = getattr(model.model, "tokenizer", None)
    if tokenizer is None:
        logger.warning("Cannot raise the tokenizer truncation limit; long messages will be cut short")
        return
    tokenizer.enable_truncation(max_length=MAX_TOKENS)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts, order preserved. Blocking: runs the ONNX session on the calling thread."""
    if not texts:
        return []
    with _model_lock:
        model = _load()
        return [_unit(vector.tolist()) for vector in model.embed(texts, batch_size=min(len(texts), 32))]


def _unit(vector: list[float]) -> list[float]:
    """Scale to unit length: fastembed mean-pools without normalizing, and vec0 ranks on L2."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


async def aembed(text: str) -> list[float]:
    """Embed a single text without blocking the event loop."""
    return (await asyncio.to_thread(embed_texts, [text]))[0]


async def aembed_texts(texts: list[str]) -> list[list[float]]:
    """Embed several texts without blocking the event loop."""
    return await asyncio.to_thread(embed_texts, texts)


def warmup() -> None:
    """Download and load the model up front instead of on the first message."""
    with _model_lock:
        _load()
