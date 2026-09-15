"""Configuration loading helpers."""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib as _toml
except Exception:
    try:
        import toml as _toml  # type: ignore
    except Exception:
        _toml = None

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    print(
        "Warning: python-dotenv not installed, environment variables from .env will not be loaded."
    )


CONFIG_PATH = Path("config.toml")
DB_PATH = Path("db/colloscope.db")


def _load_toml() -> dict[str, Any]:
    """Load and parse a TOML configuration file.

    Returns
    -------
    Dict[str, Any]
        Parsed TOML content or an empty dict.
    """

    if _toml is None:
        return {}
    if CONFIG_PATH.exists():
        with open(
            CONFIG_PATH,
            "rb"
            if hasattr(_toml, "loads")
            and _toml is not None
            and hasattr(_toml, "__name__")
            and _toml.__name__ == "tomllib"
            else "r",
            encoding=None
            if hasattr(_toml, "loads")
            and _toml is not None
            and hasattr(_toml, "__name__")
            and _toml.__name__ == "tomllib"
            else "utf-8",
        ) as f:
            # tomllib expects bytes I/O in py3.11, toml package expects text
            if getattr(_toml, "__name__", "") == "tomllib":
                return _toml.load(f)
            else:
                return _toml.load(f)
    return {}


def read_from_toml_config(
    param: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Read a nested config table from TOML data.

    Parameters
    ----------
    param : str
        Section name to read.
    config : Optional[Dict[str, Any]]
        Preloaded config mapping. Default is None.

    Returns
    -------
    Dict[str, Any]
        Section contents or an empty dict.
    """
    cfg = config or _load_toml()
    return cfg.get(param, {}) if isinstance(cfg.get(param, {}), dict) else {}


@dataclass
class ConsoleLoggingConfig:
    """Console logging configuration.

    Attributes
    ----------
    enable : bool
        Whether console logging is enabled.
    level : str
        Console logging level.
    console_format : str
        Format string used for console logs.
    """

    enable: bool = True
    level: str = "INFO"
    console_format: str = "%(asctime)s - %(message)s"


@dataclass
class FileLoggingConfig:
    """File logging configuration.

    Attributes
    ----------
    enable_file_logging : bool
        Whether file logging is enabled.
    log_file : str
        Path to the log file.
    file_format : str
        Format string used for file logs.
    """

    enable_file_logging: bool = True
    log_file: str = "logs/bot.log"

    # file logs can keep more context; filename is more useful than logger name
    file_format: str = "%(asctime)s - %(filename)s - %(message)s"


@dataclass
class DiscordLoggingConfig:
    """Discord webhook logging configuration.

    Attributes
    ----------
    enable_discord_logging : bool
        Whether Discord logging is enabled.
    discord_webhook : Optional[str]
        Discord webhook URL.
    discord_format : str
        Format string used for Discord logs.
    """

    enable_discord_logging: bool = False
    discord_webhook: str | None = None
    discord_format: str = "%(asctime)s - %(filename)s\n%(message)s"


@dataclass
class LoggingConfig:
    """Aggregated logging configuration.

    Attributes
    ----------
    console : ConsoleLoggingConfig
        Console logging settings.
    file : FileLoggingConfig
        File logging settings.
    discord : DiscordLoggingConfig
        Discord logging settings.
    level : str
        Console logging level.
    enable_file_logging : bool
        Whether file logging is enabled.
    log_file : str
        Log file path.
    enable_discord_logging : bool
        Whether Discord logging is enabled.
    discord_webhook : Optional[str]
        Discord webhook URL.
    console_format : str
        Console log format string.
    file_format : str
        File log format string.
    discord_format : str
        Discord log format string.
    """

    console: ConsoleLoggingConfig
    file: FileLoggingConfig
    discord: DiscordLoggingConfig

    @property
    def level(self) -> str:
        """Return the configured console log level.

        Returns
        -------
        str
            Console log level string.
        """
        return self.console.level

    @property
    def enable_file_logging(self) -> bool:
        """Return whether file logging is enabled.

        Returns
        -------
        bool
            True when file logging is enabled.
        """
        return self.file.enable_file_logging

    @property
    def log_file(self) -> str:
        """Return the file logging path.

        Returns
        -------
        str
            File logging path.
        """
        return self.file.log_file

    @property
    def enable_discord_logging(self) -> bool:
        """Return whether Discord logging is enabled.

        Returns
        -------
        bool
            True when Discord logging is enabled.
        """
        return self.discord.enable_discord_logging

    @property
    def discord_webhook(self) -> str | None:
        """Return the configured Discord webhook URL.

        Returns
        -------
        Optional[str]
            Discord webhook URL or None.
        """
        return self.discord.discord_webhook

    @property
    def console_format(self) -> str:
        """Return the console log format string.

        Returns
        -------
        str
            Console log format string.
        """
        return self.console.console_format

    @property
    def file_format(self) -> str:
        """Return the file log format string.

        Returns
        -------
        str
            File log format string.
        """
        return self.file.file_format

    @property
    def discord_format(self) -> str:
        """Return the Discord log format string.

        Returns
        -------
        str
            Discord log format string.
        """
        return self.discord.discord_format


@dataclass
class Config:
    """Runtime config values resolved from environment and files.

    Attributes
    ----------
    BOT_TOKEN : Optional[str]
        Discord bot token.
    WEBHOOK_POSTURL : Optional[str]
        Webhook path or id component.
    WEBHOOK_URL : Optional[str]
        Resolved webhook URL.
    BASE_DIR : str
        Repository base directory.
    CONFIG_PATH : str
        Path to the active config file.
    DB_PATH : str
        Path of the colloscope DB
    """

    BOT_TOKEN: str
    WEBHOOK_POSTURL: str | None
    WEBHOOK_URL: str | None

    CUR: sqlite3.Cursor | None = None
    CONN: sqlite3.Connection | None = None


def _first_table(items: Any) -> dict[str, Any]:
    """Return the first dict from a TOML table-or-list value.

    Parameters
    ----------
    items : Any
        Value extracted from TOML.

    Returns
    -------
    Dict[str, Any]
        First mapping if available, otherwise an empty dict.
    """
    if isinstance(items, list) and items:
        return items[0] if isinstance(items[0], dict) else {}
    if isinstance(items, dict):
        return items
    return {}


def _normalize_webhook_url(url: str | None) -> str | None:
    """Normalize a Discord webhook URL or webhook id/path.

    Parameters
    ----------
    url : Optional[str]
        Input URL or webhook reference.

    Returns
    -------
    Optional[str]
        Normalized webhook URL or None.
    """
    if not url:
        return None
    # If the configured url contains a placeholder, substitute with env var WEBHOOK_URL
    if "<URL>" in url:
        env_val = os.getenv("WEBHOOK_URL")
        if not env_val:
            return None
        url = url.replace("<URL>", env_val)
    if url.startswith(("http://", "https://")):
        return url
    return f"https://discord.com/api/webhooks/{url.lstrip('/')}"


def load_config() -> tuple[Config, LoggingConfig]:
    """Load application and logging configuration.

    Parameters
    ----------
    config_path : Optional[str]
        Optional path to a TOML config file. Default is None.

    Returns
    -------
    Tuple[Config, LoggingConfig]
        Resolved app config and logging config.
    """
    raw = _load_toml()

    raw_logging = raw.get("logging", {}) if isinstance(raw, dict) else {}
    console_raw = _first_table(raw.get("console"))
    file_raw = _first_table(raw.get("file"))
    discord_raw = _first_table(raw.get("discord"))

    # Backward compatibility with previous flat schema if present under [logging]
    console_conf = ConsoleLoggingConfig(
        enable=console_raw.get("enable", raw_logging.get("enable", True)),
        level=console_raw.get("level", raw_logging.get("level", "INFO")),
        console_format=console_raw.get(
            "console_format",
            raw_logging.get("console_format", "%(asctime)s - %(message)s"),
        ),
    )
    file_conf = FileLoggingConfig(
        enable_file_logging=file_raw.get(
            "enable_file_logging", raw_logging.get("enable_file_logging", True)
        ),
        log_file=file_raw.get("log_file", raw_logging.get("log_file", "logs/bot.log")),
        file_format=file_raw.get(
            "file_format",
            raw_logging.get("file_format", "%(asctime)s - %(filename)s - %(message)s"),
        ),
    )
    discord_conf = DiscordLoggingConfig(
        enable_discord_logging=discord_raw.get(
            "enable_discord_logging",
            raw_logging.get("enable_discord_logging", False),
        ),
        discord_webhook=_normalize_webhook_url(
            discord_raw.get("discord_webhook")
            or raw_logging.get("discord_webhook")
            or None
        ),
        discord_format=discord_raw.get(
            "discord_format",
            raw_logging.get(
                "discord_format", "%(asctime)s - %(filename)s\n%(message)s"
            ),
        ),
    )

    logging_conf = LoggingConfig(
        console=console_conf,
        file=file_conf,
        discord=discord_conf,
    )

    bot_token = os.getenv("BOT_TOKEN")
    if bot_token is None:
        raise RuntimeError("No bot token provided")

    webhook_post_url = os.getenv("WEBHOOK_URL") or os.getenv("WEBHOOK_POSTURL")
    env_webhook_url = _normalize_webhook_url(os.getenv("WEBHOOK_URL"))

    webhook_url = None
    # Determine final webhook URL: priority - env WEBHOOK_URL, logging.discord_webhook, combine webhook_base + posturl
    if env_webhook_url:
        webhook_url = env_webhook_url
    elif logging_conf.discord_webhook:
        webhook_url = logging_conf.discord_webhook
    else:
        # combine base + posturl if present
        root_webhook_base = raw.get("webhook_base") or raw.get("webhook", {}).get(
            "base"
        )
        if root_webhook_base:
            # If base contains placeholder, replace with env WEBHOOK_URL
            if "<URL>" in root_webhook_base:
                env_val = os.getenv("WEBHOOK_URL")
                if env_val:
                    substituted = root_webhook_base.replace("<URL>", env_val)
                    webhook_url = _normalize_webhook_url(substituted)
            elif webhook_post_url:
                webhook_url = (
                    root_webhook_base.rstrip("/")
                    + "/"
                    + webhook_post_url.lstrip("/")
                )

    cfg = Config(
        BOT_TOKEN=bot_token,
        WEBHOOK_POSTURL=webhook_post_url,
        WEBHOOK_URL=webhook_url
    )

    return cfg, logging_conf


# load default config at import time
cfg, logging_cfg = load_config()
