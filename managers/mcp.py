"""MCP (Model-Context-Protocol) manager for external tool servers.

Loads MCP server configurations, initializes ``fastmcp.Client`` instances for
each configured server and exposes remote tools as local function metadata.
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from fastmcp import Client

from core.config import BASE_DIR
from utils.logger import get_logger

logger = get_logger()


_ENV_TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}|\$([A-Z0-9_]+)")


def _resolve_env_tokens(value: Any) -> Any:
    """Replace ``$VAR`` / ``${VAR}`` tokens with environment values.

    Values referencing a missing variable are returned as-is so callers can
    drop them explicitly.

    Returns
    -------
    Any
        The input with tokens substituted.
    """
    if not isinstance(value, str):
        return value
    return _ENV_TOKEN.sub(
        lambda m: os.environ.get(m.group(1) or m.group(2), m.group(0)),
        value,
    )


def _resolve_header_env(headers: dict[str, Any]) -> dict[str, str]:
    """Resolve env tokens in headers and drop placeholders with no value.

    An ``Authorization`` header referencing an unset key is silently removed
    so an optional API key does not break unauthenticated usage.

    Returns
    -------
    dict[str, str]
        Headers ready to send.
    """
    resolved: dict[str, str] = {}
    for key, value in headers.items():
        text = _resolve_env_tokens(value)
        if not isinstance(text, str) or not text.strip():
            continue
        if "$" in text:
            # token referencing a missing env var -> drop this header
            continue
        resolved[key] = text
    return resolved


class MCPManager:
    """Manager for MCP servers and their exposed tools."""

    def __init__(self, config_path: str | Path):
        """Create an MCPManager.

        Parameters
        ----------
        config_path : str | Path
            Path to the JSON file containing MCP server configurations.
        """
        self.config_path = Path(config_path)
        self.clients: dict[str, Client] = {}
        self.server_raw_configs: dict[str, dict[str, Any]] = {}
        self.tools_metadata: list[dict[str, Any]] = []

    def load_config(self) -> dict:
        """Load MCP configuration JSON from disk.

        Returns
        -------
        dict
            Parsed JSON object or empty dict if the file is missing.
        """
        if not self.config_path.exists():
            logger.warning("MCP config not found at %s", self.config_path)
            return {}
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _prepare_runtime_env(self, base_env: dict[str, str]) -> dict[str, str]:
        """Prepare a runtime environment for launching MCP subprocesses.

        Ensures ``~/.microsandbox/bin`` is on ``PATH`` and sets ``MSB_PATH``
        when the microsandbox binary is available.

        Returns
        -------
        dict[str, str]
            Modified environment dictionary.
        """
        env = base_env.copy()
        msb_path = os.path.expanduser("~/.microsandbox/bin")
        msb_binary = os.path.join(msb_path, "msb")

        if msb_path not in env.get("PATH", ""):
            env["PATH"] = f"{msb_path}:{env.get('PATH', '')}"

        if os.path.exists(msb_binary):
            env.setdefault("MSB_PATH", msb_binary)

        return env

    async def initialize(self) -> None:
        """Initialize all configured MCP servers."""
        config = self.load_config()
        servers = config.get("mcpServers", {})

        tasks = []
        for name, srv_config in servers.items():
            tasks.append(self._initialize_server(name, srv_config))

        if tasks:
            await asyncio.gather(*tasks)

    async def _initialize_server(self, name: str, srv_config: dict[str, Any]) -> None:
        """Initialize a single MCP server and collect its tools."""
        try:
            logger.debug("Initializing MCP server: %s", name)
            self.server_raw_configs[name] = srv_config

            if "url" in srv_config:
                client_config: dict[str, Any] = {
                    "mcpServers": {
                        name: {
                            "url": _resolve_env_tokens(srv_config["url"]),
                            "headers": _resolve_header_env(srv_config.get("headers", {})),
                        }
                    }
                }
            else:
                env = self._prepare_runtime_env(os.environ.copy())
                env.update({k: _resolve_env_tokens(v) for k, v in srv_config.get("env", {}).items()})
                client_config = {
                    "mcpServers": {
                        name: {
                            "command": srv_config["command"],
                            "args": srv_config.get("args", []),
                            "env": env,
                        }
                    }
                }

            client = Client(client_config)
            self.clients[name] = client

            async with client:
                tools = await client.list_tools()
                for tool in tools:
                    params = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}
                    if hasattr(params, "model_dump"):
                        params = params.model_dump()
                    self.tools_metadata.append(
                        {
                            "type": "function",
                            "function": {
                                "name": f"mcp_{name}_{tool.name}",
                                "description": tool.description,
                                "parameters": params,
                            },
                        }
                    )
                logger.debug("Loaded %d tools from %s", len(tools), name)
        except Exception:
            logger.exception("Failed to initialize MCP server %s", name)

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on a remote MCP server and return its result.

        Parameters
        ----------
        server_name : str
            Logical name of the configured MCP server.
        tool_name : str
            Name of the tool to invoke on the remote server.
        arguments : dict[str, Any]
            Arguments to pass to the tool.

        Returns
        -------
        str
            Stringified result or an error message on failure.
        """
        client = self.clients.get(server_name)
        if not client:
            logger.error("MCP tool call failed: server '%s' not found", server_name)
            return f"Error: MCP server {server_name} not found."

        try:
            async with client:
                try:
                    result = await client.call_tool(tool_name, arguments, timeout=60)
                    logger.info(
                        "MCP tool %s.%s returned: %s...",
                        server_name,
                        tool_name,
                        str(result)[:500],
                    )
                    return str(result)
                except Exception as inner:
                    logger.exception(
                        "Error calling tool %s on %s",
                        tool_name,
                        server_name,
                    )
                    return f"Error: {inner!s}"
        except Exception as exc:
            logger.exception(
                "Error calling MCP tool %s on %s",
                tool_name,
                server_name,
            )
            return f"Error: {exc!s}"


# Singleton instance
MCP_CONFIG_PATH = BASE_DIR / "config" / "mcp.json"
mcp_manager = MCPManager(MCP_CONFIG_PATH)
