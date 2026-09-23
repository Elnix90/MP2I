import asyncio
import os
import time

import discord
from discord import app_commands

from cmds._shared import (
    defer_interaction,
    log_command_end,
    log_command_error,
    log_command_start,
    send_interaction,
)
from core.config import DEFAULT_BRANCH, DEFAULT_REMOTE, MAX_OUTPUT_LEN, UPDATE_TIMEOUT
from core.exec_shell_command import exec_shell_command
from core.perms import is_bot_admin
from utils.logger import get_logger

logger = get_logger()

RESTART_DELAY = 10.0


async def _restart_in(delay: float, restart_cmd: str) -> None:
    await asyncio.sleep(delay)
    if restart_cmd:
        logger.info("Redémarrage planifié du bot : %s", restart_cmd)
        try:
            result = await exec_shell_command(restart_cmd, timeout=30.0)
            if "exit code" in result:
                logger.warning("Redémarrage en échec : %s", result[:500])
            else:
                logger.info("Redémarrage : %s", result[:500])
        except Exception as exc:
            logger.error("Redémarrage échoué : %s", exc)
        return

    logger.warning("Aucune commande de redémarrage configurée : arrêt forcé du processus - Wings/AzurBOX doit redémarrer le serveur via son auto-restart.")
    os._exit(1)


async def setup(tree: app_commands.CommandTree, bot):
    @tree.command(
        name="self-update",
        description="Met à jour le bot depuis le dépôt distant",
    )
    @app_commands.describe(
        branch="Branche cible de la mise à jour (défaut: prod)",
        force="Inclut git clean -fd dans la mise à jour",
        restart="Redémarre le bot après la mise à jour",
    )
    @app_commands.check(is_bot_admin)
    async def self_update(
        interaction: discord.Interaction,
        branch: str | None = None,
        force: bool = False,
        restart: bool = False,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "self_update", interaction)

        try:
            target_branch = branch or DEFAULT_BRANCH
            target_remote = DEFAULT_REMOTE

            await defer_interaction(interaction)

            steps = _build_steps(target_remote, target_branch, do_clean=force)
            output = ""
            failed = False
            failed_step = None
            restart_cmd = os.getenv("BOT_RESTART_CMD", "")

            for step_name, step_cmd in steps:
                output += f"🔧 {step_name}...\n"
                result = await exec_shell_command(step_cmd, timeout=UPDATE_TIMEOUT)
                output += f"   {result[:1000]}\n\n"

                if result and "exit code" in result:
                    failed = True
                    failed_step = step_name
                    break

                if "timed out" in result.lower():
                    failed = True
                    failed_step = step_name
                    output += "   ⏰ Cette étape a dépassé le délai autorisé.\n\n"
                    break

            will_restart = restart and not failed

            if failed and failed_step:
                output += f"\n❌ **Échec à l'étape :** `{failed_step}`\n"
                output += f"Résultat :\n```\n{output[-MAX_OUTPUT_LEN:]}\n```"
            else:
                output += f"\n✅ **Mise à jour terminée** (branche `{target_branch}`)"
                if will_restart:
                    output += f" — redémarrage planifié dans {RESTART_DELAY:.0f}s"
                    if not restart_cmd:
                        output += " via l'auto-restart Wings (arrêt forcé, aucun BOT_RESTART_CMD)"
                    output += "."
                else:
                    output += "."

            await send_interaction(
                interaction,
                content=f"```\n{output[-MAX_OUTPUT_LEN:]}\n```",
                ephemeral=not will_restart,
            )
            if will_restart:
                asyncio.create_task(_restart_in(RESTART_DELAY, restart_cmd))

            log_command_end(
                logger,
                "self_update",
                start_time,
                status="failed" if failed else "ok",
            )
            return

        except Exception as exc:
            log_command_error(logger, "self_update", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "Error while executing the command.",
                )
            else:
                await interaction.followup.send("Error while executing the command.")


def _build_steps(remote: str, branch: str, do_clean: bool = False) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []

    steps.append(
        (
            "Vérification du dépôt",
            f"git -C {os.getcwd()} rev-parse --is-inside-work-tree 2>/dev/null || echo 'not_a_repo'",
        )
    )
    steps.append(
        (
            "Reset des remotes",
            f"git -C {os.getcwd()} remote | while read r; do git -C {os.getcwd()} remote remove $r; done",
        )
    )
    steps.append(("Ajout du remote", f"git -C {os.getcwd()} remote add origin {remote}"))
    steps.append(("Fetch", f"git -C {os.getcwd()} fetch origin --depth=1"))
    steps.append((f"Checkout de la branche {branch}", f"git -C {os.getcwd()} checkout {branch}"))
    steps.append(
        (
            f"Reset sur origin/{branch}",
            f"git -C {os.getcwd()} reset --hard origin/{branch}",
        )
    )
    if do_clean:
        steps.append(("Nettoyage des fichiers non suivis", f"git -C {os.getcwd()} clean -fd"))
    steps.append(("Vérification de la version", f"git -C {os.getcwd()} rev-parse --short HEAD"))

    steps.append(
        (
            "Mise à jour du binaire renderer (prebuilt)",
            "bash scripts/update_renderer.sh",
        )
    )

    return steps
