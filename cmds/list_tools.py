"""List all tools exposed to the model."""

import time

import discord

from cmds._shared import defer_interaction, log_command_end, log_command_error, log_command_start, send_interaction
from core.ai.tools import get_combined_tools
from utils.logger import get_logger

logger = get_logger()


async def setup(tree: discord.app_commands.CommandTree, bot):
    @tree.command(name="list-tools", description="Liste les outils disponibles pour l'IA")
    async def list_tools(interaction: discord.Interaction):
        start_time = time.perf_counter()
        log_command_start(logger, "list-tools", interaction)

        await defer_interaction(interaction, ephemeral=True)

        try:
            tools = get_combined_tools()

            if not tools:
                await send_interaction(
                    interaction,
                    content="Aucun outil disponible.",
                    ephemeral=True,
                )
                log_command_end(logger, "list-tools", start_time, status="empty")
                return

            normalized = []
            for t in tools:
                try:
                    if isinstance(t, dict) and t.get("type") == "function" and isinstance(t.get("function"), dict):
                        fn = t["function"]
                        name = fn.get("name")
                        desc = fn.get("description", "Pas de description")
                    else:
                        name = t.get("name") if isinstance(t, dict) else None
                        desc = t.get("description", "Pas de description") if isinstance(t, dict) else str(t)
                    if name:
                        normalized.append({"name": name, "description": desc})
                except Exception as exc:
                    logger.debug("Skipping malformed tool entry: %s", exc)

            native_tools = [t for t in normalized if not t["name"].startswith("mcp_")]
            mcp_tools = [t for t in normalized if t["name"].startswith("mcp_")]

            embeds = []
            if native_tools:
                embed = discord.Embed(
                    title="Outils natifs",
                    color=discord.Color.blurple(),
                    description="Outils embarqués",
                )
                for tool in native_tools:
                    embed.add_field(
                        name=f"`{tool['name']}`",
                        value=tool["description"],
                        inline=False,
                    )
                embeds.append(embed)

            if mcp_tools:
                embed = discord.Embed(
                    title="Outils MCP",
                    color=discord.Color.green(),
                    description="Outils fournis par des serveurs MCP",
                )
                for i, tool in enumerate(mcp_tools):
                    if i > 0 and i % 24 == 0:
                        embeds.append(embed)
                        embed = discord.Embed(
                            title="Outils MCP (suite)",
                            color=discord.Color.green(),
                        )
                    embed.add_field(
                        name=f"`{tool['name']}`",
                        value=tool["description"],
                        inline=False,
                    )
                if len(embed.fields):
                    embeds.append(embed)

            await send_interaction(interaction, embeds=embeds[:10], ephemeral=True)
            for embed in embeds[10:]:
                await interaction.followup.send(embed=embed, ephemeral=True)

            log_command_end(logger, "list-tools", start_time)
        except Exception as exc:
            log_command_error(logger, "list-tools", exc)
            await interaction.followup.send(
                "Erreur pendant la liste des outils.",
                ephemeral=True,
            )
