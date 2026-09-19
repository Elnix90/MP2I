"""Configuration loading helpers."""

import os
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from config.ai_conf import load_ai_config
from config.logging_conf import LoggingConfig, _normalize_webhook_url, load_logging_config
from config.perms_conf import load_perms_config

_ENV_FILE = Path(".env")
_LOCAL_ENV_FILE = Path(".env.local")
BASE_DIR = Path(__file__).parent.parent
DB_PATH = Path("data/colloscope.db")
BOT_STATE_DB_PATH = Path("data/bot_state.db")
MAX_OUTPUT_LEN = 1900
DEFAULT_REMOTE = os.getenv("BOT_REMOTE_URL", "https://github.com/Elnix90/MP2I.git")
DEFAULT_BRANCH = os.getenv("BOT_UPDATE_BRANCH", "prod")
UPDATE_TIMEOUT = float(os.getenv("BOT_UPDATE_TIMEOUT", "120"))


class Env(Enum):
    PROD = True
    LOCAL = False


def _load_env_files() -> None:
    if os.getenv("ENV", "LOCAL").upper() == "PROD" or not _LOCAL_ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
    else:
        load_dotenv(_LOCAL_ENV_FILE)


try:
    from dotenv import load_dotenv

    _load_env_files()
except Exception:
    print(
        "Warning: python-dotenv not installed, environment variables from .env files will not be loaded.",
    )

ENV = Env.PROD if os.getenv("ENV", "LOCAL").upper() == "PROD" else Env.LOCAL


@dataclass
class Config:
    BOT_TOKEN: str
    GUILD_ID: int
    WEBHOOK_POSTURL: str | None
    WEBHOOK_URL: str | None
    DEBUG_MODE: bool = False
    CUR: sqlite3.Cursor | None = None
    CONN: sqlite3.Connection | None = None
    AI_API_KEY: str | None = None
    AI_ENABLED: bool = True
    AI_ALLOWED_CHANNELS: list[int] = field(default_factory=list)
    AI_MODEL: str = ""
    AI_MODELS: list[str] = field(default_factory=list)
    AI_API_URL: str = ""
    AI_SYSTEM_PROMPT: str = ""
    AI_STREAMING: bool = True
    AI_MEMORY_MAX_HISTORY: int = 15
    AI_TOOLS: list[str] = field(default_factory=list)
    AI_NEEDLE_TOOL_CALLING: bool = False


def load_config() -> tuple[Config, LoggingConfig]:
    logging_conf = load_logging_config()
    ai_conf = load_ai_config()

    bot_token = os.getenv("BOT_TOKEN")
    if bot_token is None:
        raise RuntimeError("No bot token provided")

    guild_id = os.getenv("GUILD_ID")
    if guild_id is None:
        raise RuntimeError("No guild ID provided")
    guild_id = int(guild_id)

    webhook_post_url = os.getenv("WEBHOOK_URL") or os.getenv("WEBHOOK_POSTURL")
    env_webhook_url = _normalize_webhook_url(os.getenv("WEBHOOK_URL"))

    debug_mode = os.getenv("DEBUG_MODE") == "true"

    webhook_url = None
    if env_webhook_url:
        webhook_url = env_webhook_url
    elif logging_conf.discord_webhook:
        webhook_url = logging_conf.discord_webhook

    return Config(
        BOT_TOKEN=bot_token,
        GUILD_ID=guild_id,
        AI_API_KEY=os.getenv("AI_API_KEY"),
        WEBHOOK_POSTURL=webhook_post_url,
        WEBHOOK_URL=webhook_url,
        DEBUG_MODE=debug_mode,
        AI_ENABLED=ai_conf.enabled,
        AI_ALLOWED_CHANNELS=ai_conf.allowed_channels,
        AI_MODELS=ai_conf.models,
        AI_MODEL=ai_conf.model,
        AI_API_URL=ai_conf.api_url,
        AI_SYSTEM_PROMPT=ai_conf.system_prompt,
        AI_STREAMING=ai_conf.streaming,
        AI_MEMORY_MAX_HISTORY=ai_conf.memory_max_history,
        AI_TOOLS=ai_conf.tools,
        AI_NEEDLE_TOOL_CALLING=ai_conf.needle_tool_calling,
    ), logging_conf


cfg, logging_cfg = load_config()
perms_cfg = load_perms_config()
