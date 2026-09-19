"""Health command handlers.

Registers the ``/health`` command which performs runtime checks for the AI
subsystems (Discord, memory, tools, MCP) and reports status.
"""

import time

import discord

from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
)
from core.ai.tools import get_combined_tools, tools_loader
from managers.mcp import mcp_manager
from utils.logger import get_logger

logger = get_logger()


def _status_label(ok: bool) -> str:
    """Return a human-readable status label."""
    return "Healthy" if ok else "Degraded"


async def setup(tree: discord.app_commands.CommandTree, bot):
    """Register the ``health`` command on the provided command tree."""

    @tree.command(name="health", description="Statut de santé des sous-systèmes du bot")
    async def health(interaction: discord.Interaction):
        """Perform runtime health checks and reply with a summary embed."""
        start_time = time.perf_counter()
        log_command_start(logger, "health", interaction)

        await defer_interaction(interaction)

        try:
            gateway_ms = round(bot.latency * 1000, 2)
            discord_ok = bot.is_ready()

            memory_ok = True
            memory_note = "OK"
            memory_turns = 0
            try:
                memory_turns = len(bot.memory.list_turns(limit=50))
            except Exception as exc:
                memory_ok = False
                memory_note = f"Error: {exc}"

            native_declared = len(tools_loader.tools_metadata)
            native_loaded = len(tools_loader.tools_handlers)
            tools_ok = native_loaded == native_declared

            mcp_tool_count = sum(
                1
                for tool in mcp_manager.tools_metadata
                if tool.get("function", {}).get("name", "").startswith("mcp_")
            )
            combined_tools = get_combined_tools()

            configured_servers = len(mcp_manager.load_config().get("mcpServers", {}))
            connected_servers = len(mcp_manager.clients)
            mcp_ok = connected_servers == configured_servers

            overall_ok = discord_ok and memory_ok and tools_ok and mcp_ok

            embed = discord.Embed(
                title="Health Check",
                color=discord.Color.green() if overall_ok else discord.Color.orange(),
                description=f"Statut global : **{_status_label(overall_ok)}**",
            )
            embed.add_field(
                name="Discord",
                value=f"Statut : {_status_label(discord_ok)}\nLatence : {gateway_ms} ms",
                inline=False,
            )
            embed.add_field(
                name="Mémoire",
                value=(
                    f"Statut : {_status_label(memory_ok)}\n"
                    f"Turns en mémoire : {memory_turns}\n"
                    f"Détail : {memory_note}"
                ),
                inline=False,
            )
            embed.add_field(
                name="Outils",
                value=(
                    f"Statut : {_status_label(tools_ok)}\n"
                    f"Natifs déclarés/chargés : {native_declared}/{native_loaded}\n"
                    f"Outils MCP : {mcp_tool_count}\n"
                    f"Total exposés : {len(combined_tools)}"
                ),
                inline=False,
            )
            embed.add_field(
                name="MCP",
                value=(
                    f"Statut : {_status_label(mcp_ok)}\n"
                    f"Serveurs configurés : {configured_servers}\n"
                    f"Clients connectés : {connected_servers}"
                ),
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            log_command_end(
                logger, "health", start_time, status=_status_label(overall_ok)
            )
        except Exception as exc:
            log_command_error(logger, "health", exc)
            try:
                await interaction.followup.send(
                    "Erreur pendant le health check.", ephemeral=True
                )
            except Exception as send_exc:
                logger.error("Failed to send error message: %s", send_exc)
