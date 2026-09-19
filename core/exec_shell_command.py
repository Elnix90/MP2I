"""Execute a shell command on the bot's host and capture its output.

Commands are parsed with `shlex` and checked against token-based deny rules
before running: destructive commands, remote code execution and reads of
secret files are blocked with a human-readable reason. This guard stops
mistakes and lazy probing, not a determined attacker — the endpoint must stay
strictly admin-only.
"""

import asyncio
import shlex
from pathlib import Path

DEFAULT_TIMEOUT = 30.0

_SEPARATORS = frozenset({"|", "&", "&&", "||", ";", "(", ")"})
_REDIRECTS = frozenset({">", "<"})
_UNWRAP = frozenset({"sudo", "env", "time", "nohup", "command"})

_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
_READERS = frozenset(
    {
        "cat",
        "head",
        "tail",
        "more",
        "less",
        "strings",
        "grep",
        "rg",
        "sed",
        "awk",
        "vi",
        "vim",
        "nano",
        "base64",
        "xxd",
        "od",
        "hexdump",
        "type",
    },
)
_INTERPRETERS = frozenset(
    {"python", "python2", "python3", "pypy", "perl", "ruby", "php", "node"}
)
_DOWNLOADERS = frozenset({"curl", "wget"})
_REVERSE_SHELLS = frozenset({"nc", "ncat", "socat"})
_SYSTEM_STOP = frozenset({"shutdown", "reboot", "halt", "poweroff"})
_COPY_WRITERS = frozenset({"cp", "mv", "install", "tee"})

_INLINE_FLAGS = frozenset({"-c", "-e", "-p", "-r"})
_RM_AT_ROOT = frozenset({"/", "~", "$HOME", "*"})

_SECRET_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        ".htpasswd",
    },
)
_SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".key", ".htpasswd")
_AUTH_FILES = frozenset({"/etc/shadow", "/etc/passwd", "/etc/gshadow", "/etc/sudoers"})


def _tokenize(cmd: str) -> list[str]:
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _effective(tokens: list[str]) -> tuple[str, list[str]]:
    for index, token in enumerate(tokens):
        if token not in _UNWRAP:
            return token, tokens[index + 1 :]
    return "", []


def _segments(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _SEPARATORS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _is_private(arg: str) -> bool:
    name = Path(arg).name.lower()
    if name in _SECRET_NAMES:
        return True
    if arg in _AUTH_FILES:
        return True
    if arg.lower().endswith(_SECRET_SUFFIXES):
        return True
    return "/.ssh/" in arg


def _blocked_reason(cmd: str) -> str | None:
    if "$(" in cmd or "`" in cmd:
        return "substitution de commande ($( ) / backticks)"
    if "/dev/tcp/" in cmd:
        return "network backdoor (/dev/tcp)"
    if ":(){" in cmd.replace(" ", ""):
        return "fork bomb"

    try:
        tokens = _tokenize(cmd)
    except ValueError:
        return "quoting incomplet"

    for index, token in enumerate(tokens):
        if token == "|":
            left = _effective(tokens[:index])[0]
            right = tokens[index + 1 :]
            if left in _DOWNLOADERS and right and right[0] in _SHELLS:
                return "remote payload piped to a shell"

    for index, token in enumerate(tokens):
        if token in _REDIRECTS:
            target_index = index + 1
            while target_index < len(tokens) and tokens[target_index] in _REDIRECTS:
                target_index += 1
            if target_index < len(tokens) and tokens[target_index] in _AUTH_FILES:
                return "write to system auth files"

    for segment in _segments(tokens):
        command, args = _effective(segment)
        lowered = command.lower()

        if lowered in _SYSTEM_STOP:
            return "system shutdown/reboot"
        if lowered == "init" and any(arg in {"0", "6"} for arg in args):
            return "system shutdown/reboot"
        if lowered.startswith("mkfs"):
            return "filesystem formatting"
        if lowered == "dd" and any(
            arg.startswith("of=") and arg[3:].startswith("/dev/") for arg in args
        ):
            return "raw device write"
        if lowered == "rm":
            flags = [
                arg for arg in args if arg.startswith("-") and not arg.startswith("--")
            ]
            if any("r" in flag and "f" in flag for flag in flags):
                return "recursive/forced delete"
            if any(arg in _RM_AT_ROOT for arg in args):
                return "delete at filesystem root"
        if lowered in _REVERSE_SHELLS and "-e" in args:
            return "reverse shell (-e backdoor)"
        if lowered in _INTERPRETERS and any(
            arg.lower() in _INLINE_FLAGS for arg in args
        ):
            return "inline script execution"
        if lowered in _READERS and any(_is_private(arg) for arg in args):
            return "lecture d'un fichier privé (clés, tokens, .env)"
        if lowered == "chmod" and "/" in args and any(arg.isdigit() for arg in args):
            return "chmod at filesystem root"
        if lowered == "chown" and "/" in args and "-R" in args:
            return "recursive chown at filesystem root"
        if lowered in _COPY_WRITERS and any(arg in _AUTH_FILES for arg in args):
            return "write to system auth files"

    return None


async def exec_shell_command(cmd: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    blocked = _blocked_reason(cmd)
    if blocked:
        return f"Command blocked: {blocked}"

    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return f"Command timed out after {timeout:g}s"

    output = stdout.decode(errors="replace").strip()

    if process.returncode:
        status = f"[exit code {process.returncode}]"
        output = f"{output}\n{status}" if output else status

    return output or "(no output)"
