"""Tool registry for the AI layer.

Combines native tools (loaded from ``config/tools/*.json``) with MCP tools
exposed by ``managers.mcp``.
"""

import json

from managers.tools import get_tools_loader
from utils.logger import get_logger

logger = get_logger()

tools_loader = get_tools_loader()


def get_combined_tools() -> list[dict]:
    """Return the full list of tools exposed to the model.

    Returns
    -------
    list[dict]
        Combined native + MCP tool descriptors.
    """
    from managers.mcp import mcp_manager

    return tools_loader.tools_metadata + mcp_manager.tools_metadata


async def handle_tool_call(tool_name: str, args: dict) -> str:
    """Execute a tool requested by the model.

    Routes native tools directly, and ``mcp_<server>_<tool>`` names to the
    matching MCP server.

    Parameters
    ----------
    tool_name : str
        Tool name to execute.
    args : dict
        Arguments forwarded to the tool.

    Returns
    -------
    str
        Tool result string or error message.
    """
    try:
        if tool_name.startswith("mcp_"):
            from managers.mcp import mcp_manager

            parts = tool_name.split("_", 2)
            if len(parts) >= 3:
                server_name = parts[1]
                actual_tool_name = parts[2]
                return await mcp_manager.call_tool(server_name, actual_tool_name, args)

        if tool_name in tools_loader.tools_handlers:
            return await tools_loader.call_tool(tool_name, args)

        return "Unknown tool."
    except Exception as exc:
        logger.error("Error in tool %s: %s", tool_name, exc)
        return f"Error during tool {tool_name} execution: {exc!s}"


def parse_tool_arguments(arguments: str) -> dict:
    """Parse a tool-call arguments JSON string.

    Parameters
    ----------
    arguments : str
        Serialized JSON arguments from the model.

    Returns
    -------
    dict
        Parsed arguments, or {} on failure.
    """
    try:
        loaded = json.loads(arguments)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        logger.warning("Invalid tool arguments JSON: %s", arguments[:200])
        return {}
