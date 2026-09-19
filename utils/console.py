"""Interactive console for the bot.

Lets an operator type commands directly in the process terminal (e.g. from a
noVNC or VPS console) while the log output keeps flowing. The input line is
pinned at the bottom of the terminal and is redrawn around every log entry,
so typed text always stays visually separated from the logs.

When stdin is not a TTY the interactive input is disabled and the console
falls back to plain log output.
"""

import asyncio
import os
import subprocess
import sys
import time
from typing import Any

from core.config import BASE_DIR, ENV, Env
from utils.logger import get_logger

logger = get_logger()

_PROMPT = "\x1b[36m> \x1b[0m"
_ECHO = "\x1b[96m>> \x1b[0m"
_LF = "\n"
_CR = "\r"
_CRLF = "\r\n"
_CLEAR_LINE = "\x1b[2K"
_CLEAR_SCREEN = "\x1b[2J\x1b[H"


class Console:
    """Read stdin asynchronously and keep input separated from log output.

    Attributes
    ----------
    _loop : Optional[asyncio.AbstractEventLoop]
        Event loop the console is attached to.
    _client : Optional[Any]
        Bot client exposed to console commands.
    _started_at : Optional[float]
        Monotonic timestamp of the console boot.
    _enabled : bool
        True once the console accepts input.
    _tui : bool
        True when the raw-mode bottom-bar interface is active.
    _fd : int
        File descriptor of stdin.
    _saved_attrs : Any
        Termios attributes restored on close.
    _buffer : str
        Currently typed line.
    _esc : int
        Base counter used to skip terminal escape sequences.
    _pending : bytes
        Partial UTF-8 bytes waiting for the next read.
    _read_task : Optional[asyncio.Task]
        Background stdin reader used in line mode.
    _closing : bool
        True once the console has been shut down.

    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None
        self._started_at: float | None = None
        self._enabled = False
        self._tui = False
        self._fd = sys.stdin.fileno()
        self._saved_attrs: Any = None
        self._buffer = ""
        self._esc = 0
        self._pending = b""
        self._read_task: asyncio.Task | None = None
        self._closing = False

    @property
    def client(self) -> Any:
        """Return the bot client attached to the console.

        Returns
        -------
        Any
            The bot client, or None when none was provided.

        """
        return self._client

    # -------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------

    def attach(self, loop: asyncio.AbstractEventLoop, client: Any = None) -> None:
        """Activate the interactive console on the given event loop.

        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            Running event loop used to schedule stdin reads.
        client : Any
            Bot client to expose to console commands (default: None).

        """
        if self._enabled or self._closing:
            return
        self._loop = loop
        self._client = client
        self._started_at = time.monotonic()

        if ENV == Env.LOCAL:
            logger.info("Console interactive désactivée.")
            return
        if not sys.stdin.isatty():
            logger.info("Console interactive désactivée : stdin n'est pas un terminal.")
            return

        self._enabled = True
        if self._enter_raw_mode():
            self._tui = True
            self._render_prompt()
            loop.add_reader(self._fd, self._on_readable)
            logger.info("Console interactive active - tapez 'help'.")
        else:
            self._read_task = loop.create_task(self._read_loop())
            logger.info("Console interactive active (mode ligne) - tapez 'help'.")

    async def aclose(self) -> None:
        """Stop reading input, restore terminal settings and free the console.

        Returns
        -------
        None

        """
        self._closing = True
        try:
            if self._loop is not None and self._tui:
                self._loop.remove_reader(self._fd)
        except (OSError, RuntimeError, ValueError):
            pass
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, OSError, RuntimeError):
                pass
            self._read_task = None
        self._restore_termios()
        self._tui = False
        self._enabled = False

    def print_log(self, message: str) -> None:
        """Write a log line while keeping the input bar pinned at the bottom.

        Parameters
        ----------
        message : str
            Pre-formatted log entry to display.

        """
        if not self._tui:
            self._write(message + _LF)
            return
        lines = message.split(_LF)
        out = _CR + _CLEAR_LINE + lines[0]
        for line in lines[1:]:
            out += _CRLF + line
        out += _CRLF + _PROMPT + self._buffer
        self._write(out)

    def say(self, message: str) -> None:
        """Print an operator-facing message through the console renderer.

        Parameters
        ----------
        message : str
            Message to display.

        """
        self.print_log(message)

    # -------------------------------------------------------------
    # Rendering helpers
    # -------------------------------------------------------------

    def _write(self, text: str) -> None:
        try:
            sys.stderr.write(text)
            sys.stderr.flush()
        except (OSError, ValueError):
            pass

    def _render_prompt(self) -> None:
        self._write(_CR + _CLEAR_LINE + _PROMPT + self._buffer)

    def _enter_raw_mode(self) -> bool:
        try:
            import termios
            import tty

            self._saved_attrs = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
            return True
        except (OSError, ValueError):
            return False

    def _restore_termios(self) -> None:
        if self._saved_attrs is None:
            return
        try:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved_attrs)
        except (OSError, ValueError):
            pass
        self._saved_attrs = None

    # -------------------------------------------------------------
    # Input handling
    # -------------------------------------------------------------

    def _on_readable(self) -> None:
        try:
            raw = os.read(self._fd, 256)
        except OSError:
            return
        if not raw:
            if not self._buffer:
                self._submit("quit")
            return
        self._consume(raw)

    def _consume(self, raw: bytes) -> None:
        data = self._pending + raw
        self._pending = b""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
            for cut in range(1, len(data)):
                try:
                    text = data[:-cut].decode("utf-8")
                    self._pending = data[-cut:]
                    break
                except UnicodeDecodeError:
                    continue
            else:
                self._pending = data
        for char in text:
            self._handle_char(ord(char))

    def _handle_char(self, code: int) -> None:
        if code in (13, 10):  # Enter
            self._submit()
        elif code in (127, 8):  # Backspace
            if self._buffer:
                self._buffer = self._buffer[:-1]
                self._render_prompt()
        elif 0x20 <= code <= 0x7E or code >= 0xA0:
            self._buffer += chr(code)
            self._render_prompt()

    def _submit(self, forced: str | None = None) -> None:
        command = self._buffer.strip() if forced is None else forced
        self._buffer = ""
        if self._tui:
            self._write(_CR + _CLEAR_LINE + _ECHO + command + _CRLF + _PROMPT)
        else:
            self._write(_ECHO + command + _LF)
        if command:
            self._dispatch(command)

    async def _read_loop(self) -> None:
        """Fallback line-based reader used when raw mode is unavailable."""
        while not self._closing:
            line = (await asyncio.to_thread(sys.stdin.readline)).strip()
            if line:
                self._submit(line)
            elif not line:
                await asyncio.sleep(0.2)

    def _dispatch(self, raw: str) -> None:
        stripped = raw.strip()
        if not stripped:
            return
        if stripped.startswith("!"):
            self._run_shell(stripped[1:].strip())
            return
        parts = stripped.split(maxsplit=1)
        name = parts[0].lower()
        if name in _SHELL_NAMES:
            self._run_shell(parts[1].strip() if len(parts) > 1 else "")
            return
        entry = _ALL.get(name)
        if entry is None:
            logger.warning("Commande inconnue %r - tapez 'help'.", name)
            return
        logger.info("Commande console : %s", raw)
        args = parts[1].split() if len(parts) > 1 else []
        try:
            if self._loop is not None:
                self._loop.create_task(entry[0](self, args))
        except Exception:
            logger.exception("Erreur lors de l'exécution de la commande %r", name)

    def _run_shell(self, command: str) -> None:
        if self._loop is None:
            return
        if not command:
            logger.warning("Usage : shell <commande>  ou  ! <commande>")
            return
        logger.info("Commande console : !%s", command)
        self._loop.create_task(_cmd_shell(self, command))


# -------------------------------------------------------------
# Built-in console commands
# -------------------------------------------------------------


async def _cmd_help(console: Console, _args: list[str]) -> None:
    console.say("Commandes du terminal :")
    for name, (_fn, description) in _CMDS.items():
        console.say(f"  {name:<8} {description}")


async def _cmd_status(console: Console, _args: list[str]) -> None:
    uptime = time.monotonic() - (console._started_at or time.monotonic())
    line = f"Uptime : {uptime:.1f}s"
    client = console.client
    if client is not None:
        guilds = len(client.guilds)
        latency_ms = getattr(client, "latency", 0.0) * 1000
        line += f" - Serveurs : {guilds} - Latence : {latency_ms:.1f} ms"
    console.say(line)


async def _cmd_shutdown(console: Console, _args: list[str]) -> None:
    console.say("Arrêt du bot...")
    logger.info("Arrêt demandé depuis la console.")
    client = console.client
    try:
        if client is not None:
            await client.close()
        elif console._loop is not None:
            console._loop.stop()
    except Exception as exc:
        logger.warning("Erreur pendant l'arrêt : %s", exc)


async def _cmd_shell(console: Console, command: str) -> None:
    console.say(f"$ {command}")
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=BASE_DIR,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Commande expirée (60s) : %s", command)
        return
    output = (result.stdout + result.stderr).splitlines()
    for line in output:
        console.say(line)
    if result.returncode != 0:
        logger.warning("Commande terminée avec le code %d", result.returncode)


async def _cmd_clear(console: Console, _args: list[str]) -> None:
    console._write(_CLEAR_SCREEN)
    console._render_prompt()


_CMDS: dict[str, tuple[Any, str]] = {
    "help": (_cmd_help, "Affiche cette aide"),
    "status": (_cmd_status, "État du bot (uptime, serveurs, latence)"),
    "shell": (_cmd_shell, "Exécute une commande système (sans sudo)"),
    "shutdown": (_cmd_shutdown, "Arrête le bot proprement"),
    "clear": (_cmd_clear, "Efface l'écran"),
}

_SHELL_NAMES = {"shell", "sh", "bash", "exec"}

_ALL: dict[str, tuple[Any, str]] = dict(_CMDS)

_console = Console()


def get_console() -> Console:
    """Return the shared interactive console instance.

    Returns
    -------
    Console
        The global console singleton.

    """
    return _console
