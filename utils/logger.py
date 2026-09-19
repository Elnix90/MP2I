"""Logging helpers and Discord webhook handlers for the MP2I bot."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from logging import Handler

import colorama
from colorama import Fore, Style

from core.config import LoggingConfig

colorama.init(autoreset=True)

LOGGER_NAME = "MP2I"

_WEBHOOK_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="log-webhook",
)


class BotFilter(logging.Filter):
    """Filter log records to only keep the bot's logger output."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return True for log records emitted by the bot logger.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to inspect.

        Returns
        -------
        bool
            True when the record belongs to the MP2I logger.

        """
        return record.name == LOGGER_NAME


class ColoredFormatter(logging.Formatter):
    """Add ANSI color codes to console log messages."""

    COLORS = {  # noqa: RUF012
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with console color codes.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to format.

        Returns
        -------
        str
            Colored formatted string.

        """
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


class ConsoleHandler(Handler):
    """Route log records to the interactive console renderer.

    The console keeps typed input pinned at the bottom of the terminal while
    log lines scroll above; when no interactive console is attached the
    records are printed plainly to stderr.
    """

    def __init__(self, console, level: int = logging.NOTSET):
        """Initialize a console handler.

        Parameters
        ----------
        console : Any
            Interactive console instance used to render records.
        level : int
            Logging level threshold (default: logging.NOTSET).

        """
        super().__init__(level)
        self._console = console

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record through the console renderer.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to render.

        """
        try:
            message = self.format(record)
            self._console.print_log(message)
        except Exception:
            self.handleError(record)


class DiscordAnsiFormatter(logging.Formatter):
    """Wrap log output in a Discord-compatible ANSI code block."""

    LEVEL_COLORS = {  # noqa: RUF012
        logging.DEBUG: "\x1b[36m",
        logging.INFO: "\x1b[32m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[1;31m",
    }

    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for Discord ANSI rendering.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to format.

        Returns
        -------
        str
            ANSI wrapped code block string.

        """
        message = super().format(record)
        color = self.LEVEL_COLORS.get(record.levelno, "\x1b[37m")
        return f"```ansi\n{color}{message}{self.RESET}\n```"


class DiscordWebhookHandler(Handler):
    """Send log records to a Discord webhook."""

    def __init__(self, webhook_url: str, level: int = logging.INFO):
        """Initialize the Discord webhook handler.

        Parameters
        ----------
        webhook_url : str
            Discord webhook URL.
        level : int
            Logging level threshold (default: logging.INFO).

        """
        super().__init__(level)
        self.webhook_url = webhook_url

    def _build_payload(self, record: logging.LogRecord) -> dict:
        """Build the webhook payload for a log record.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to serialize.

        Returns
        -------
        dict
            Discord webhook payload.

        """
        message = self.format(record)
        payload = {
            "username": "MP2I Bot",
            "allowed_mentions": {"parse": []},
        }

        payload["content"] = message
        return payload

    @staticmethod
    def _split_payload_chunks(message: str, limit: int = 1900) -> list[str]:
        """Split a long Discord message into safe chunks.

        Parameters
        ----------
        message : str
            Message text to split.
        limit : int
            Maximum chunk length (default: 1900).

        Returns
        -------
        list[str]
            List of message chunks.

        """
        if len(message) <= limit:
            return [message]

        chunks: list[str] = []
        start = 0
        while start < len(message):
            end = min(start + limit, len(message))
            if end < len(message):
                newline = message.rfind("\n", start, end)
                if newline > start:
                    end = newline + 1
            chunks.append(message[start:end])
            start = end
        return chunks

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the configured Discord webhook.

        The network I/O runs on a background thread so the event loop (or
        whatever thread is logging) is never blocked by HTTP retries.

        Parameters
        ----------
        record : logging.LogRecord
            Log record to send.

        """
        try:
            payload = self._build_payload(record)
            chunks = self._split_payload_chunks(payload["content"])
            for index, chunk in enumerate(chunks, start=1):
                chunk_payload = dict(payload)
                chunk_payload["content"] = chunk
                chunk_payload["url"] = self.webhook_url
                if len(chunks) > 1:
                    chunk_payload["content"] = (
                        f"{chunk_payload['content']}\n\n[{index}/{len(chunks)}]"
                    )
                _WEBHOOK_EXECUTOR.submit(self._deliver, chunk_payload)
        except Exception:
            self.handleError(record)

    @staticmethod
    def _deliver(payload: dict) -> None:
        """POST one webhook payload with retries on rate-limits."""
        try:
            import requests

            headers = {"Content-Type": "application/json"}
            for attempt in range(3):
                response = requests.post(
                    payload["url"],
                    json=payload,
                    headers=headers,
                    timeout=8,
                )
                if response.status_code == 429:
                    retry_after = response.json().get("retry_after", 1)
                    time.sleep(float(retry_after))
                    continue
                response.raise_for_status()
                break
        except Exception as exc:
            print(f"Failed to send log to Discord webhook: {exc}")


def _is_real_webhook_url(url: str | None) -> bool:
    """Return True when the webhook URL looks like a real value.

    Parameters
    ----------
    url : Optional[str]
        Webhook URL to test.

    Returns
    -------
    bool
        True when the URL is non-empty and not a placeholder.

    """
    return bool(url) and "<URL>" not in url


def setup_logging(level: int, config: LoggingConfig):
    """Configure console, file and Discord webhook logging.

    Parameters
    ----------
    level : int
        Root logging level (default: logging.INFO).
    config : Any
        Optional configuration object with logging settings. Default is None.

    """
    console_format = config.console_format
    file_format = config.file_format
    discord_format = config.discord_format

    handlers = []

    # stream handler (interactive console when a TTY is available)
    if (
        config is None
        or getattr(config, "console", None) is None
        or getattr(config.console, "enable", True)
    ):
        # Deferred import to avoid a circular dependency between
        # utils.logger (imports the console renderer) and utils.console
        # (imports utils.logger).
        from utils.console import get_console

        handler = ConsoleHandler(get_console())
        handler.setFormatter(ColoredFormatter(console_format))
        handler.addFilter(BotFilter())
        handlers.append(handler)

    # optional file handler
    if config is not None and getattr(config, "enable_file_logging", False):
        try:
            fh = logging.FileHandler(getattr(config, "log_file", "logs/mp2i.log"))
            fh.setFormatter(logging.Formatter(file_format))
            fh.addFilter(BotFilter())
            handlers.append(fh)
        except Exception:
            pass

    webhook = config.discord_webhook
    # optional discord webhook
    if (
        webhook is not None
        and config.discord.enable_discord_logging
        and _is_real_webhook_url(webhook)
    ):
        try:
            dh = DiscordWebhookHandler(webhook)
            dh.setFormatter(DiscordAnsiFormatter(discord_format))
            handlers.append(dh)
        except Exception:
            pass

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Dynamically silence all loggers except our own
    for name in list(logging.root.manager.loggerDict.keys()):
        if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
            continue
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(logging.CRITICAL)
        lib_logger.propagate = False
        # Still attach our handlers to catch CRITICAL errors in files/discord
        for handler in handlers:
            if handler not in lib_logger.handlers:
                lib_logger.addHandler(handler)


def get_logger() -> logging.Logger:
    """Return the bot's logger instance.

    Returns
    -------
    logging.Logger
        Logger configured for bot output.

    """
    return logging.getLogger(LOGGER_NAME)
