import os
from dataclasses import dataclass, field
from pathlib import Path

import json5


def _normalize_webhook_url(url: str | None) -> str | None:
    if not url:
        return None
    if "<URL>" in url:
        env_val = os.getenv("WEBHOOK_URL")
        if not env_val:
            return None
        url = url.replace("<URL>", env_val)
    if url.startswith(("http://", "https://")):
        return url
    return f"https://discord.com/api/webhooks/{url.lstrip('/')}"


@dataclass
class ConsoleLoggingConfig:
    enable: bool = True
    level: str = "INFO"
    console_format: str = "%(asctime)s - %(message)s"


@dataclass
class FileLoggingConfig:
    enable_file_logging: bool = True
    filename_format: str = "logs/current-{date}.log"
    level: str = "DEBUG"
    file_format: str = "%(asctime)s - %(filename)s - %(message)s"


@dataclass
class DiscordLoggingConfig:
    enable_discord_logging: bool = False
    discord_webhook: str | None = None
    discord_format: str = "%(asctime)s - %(filename)s %(message)s"


@dataclass
class LoggingConfig:
    console: ConsoleLoggingConfig = field(default_factory=ConsoleLoggingConfig)
    file: FileLoggingConfig = field(default_factory=FileLoggingConfig)
    discord: DiscordLoggingConfig = field(default_factory=DiscordLoggingConfig)

    @property
    def level(self) -> str:
        return self.console.level

    @property
    def enable_file_logging(self) -> bool:
        return self.file.enable_file_logging

    @property
    def log_file(self) -> str:
        return self.file.filename_format

    @property
    def enable_discord_logging(self) -> bool:
        return self.discord.enable_discord_logging

    @property
    def discord_webhook(self) -> str | None:
        return self.discord.discord_webhook

    @property
    def console_format(self) -> str:
        return self.console.console_format

    @property
    def file_format(self) -> str:
        return self.file.file_format

    @property
    def discord_format(self) -> str:
        return self.discord.discord_format


def load_logging_config(file: Path | None = None) -> LoggingConfig:
    path = file or Path("config/logging_config.json5")
    with open(path) as f:
        raw = json5.load(f)

    logging_raw = raw.get("logging", raw)

    console_raw = logging_raw.get("console", {})
    console = ConsoleLoggingConfig(
        enable=console_raw.get("enable", True),
        level=console_raw.get("level", "INFO"),
        console_format=console_raw.get(
            "format",
            console_raw.get("console_format", "%(asctime)s - %(message)s"),
        ),
    )

    file_raw = logging_raw.get("file", {})
    file_conf = FileLoggingConfig(
        enable_file_logging=file_raw.get("enable", True),
        filename_format=file_raw.get("filename_format", file_raw.get("file", "logs/current-{date}.log")),
        level=file_raw.get("level", "DEBUG"),
        file_format=file_raw.get(
            "format",
            file_raw.get("file_format", "%(asctime)s - %(filename)s - %(message)s"),
        ),
    )

    discord_raw = logging_raw.get("discord", {})
    discord = DiscordLoggingConfig(
        enable_discord_logging=discord_raw.get("enable", False),
        discord_webhook=_normalize_webhook_url(discord_raw.get("webhook")),
        discord_format=discord_raw.get(
            "format",
            discord_raw.get("discord_format", "%(asctime)s - %(filename)s %(message)s"),
        ),
    )

    return LoggingConfig(console=console, file=file_conf, discord=discord)
