"""Execute a shell command on the bot's host and capture its output."""

import asyncio

DEFAULT_TIMEOUT = 30.0


async def exec_shell_command(cmd: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Run a shell command and return its combined stdout/stderr.

    Parameters
    ----------
    cmd : str
        Shell command to execute.
    timeout : float
        Maximum number of seconds to wait for the command (default 30).

    Returns
    -------
    str
        Combined standard output and standard error, or a message if the
        command timed out or produced no output.

    """
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
