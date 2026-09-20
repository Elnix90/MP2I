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

from utils.logger import get_logger

logger = get_logger()


_ENV_TOKEN = re.compile(r"\$\{([A-Z0-9_]+)\}|\$([A-Z0-9_]+)")


def _resolve_env_tokens(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _ENV_TOKEN.sub(
        lambda m: os.environ.get(m.group(1) or m.group(2), m.group(0)),
        value,
    )


def _resolve_header_env(headers: dict[str, Any]) -> dict[str, str]:
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
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.clients: dict[str, Client] = {}
        self.server_raw_configs: dict[str, dict[str, Any]] = {}
        self.tools_metadata: list[dict[str, Any]] = []

    def load_config(self) -> dict:
        if not self.config_path.exists():
            logger.warning("MCP config not found at %s", self.config_path)
            return {}
        with self.config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    async def initialize(self) -> None:
        config = self.load_config()
        servers = config.get("mcpServers", {})

        tasks = []
        for name, srv_config in servers.items():
            tasks.append(self._initialize_server(name, srv_config))

        if tasks:
            await asyncio.gather(*tasks)

    async def _initialize_server(self, name: str, srv_config: dict[str, Any]) -> None:
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
                env = os.environ.copy()
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
        client = self.clients.get(server_name)
        if not client:
            logger.error("MCP tool call failed: server '%s' not found", server_name)
            return f"Error: MCP server {server_name} not found."

        try:
            async with client:
                try:
                    result = await client.call_tool(tool_name, arguments, timeout=60)
                    logger.debug(
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


mcp_manager = MCPManager(Path("config/mcp.json"))
