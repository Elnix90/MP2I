"""Edit a single planning row.

Provides a `setup` function to register the `/colle edit` subcommand, which
modifies the room, day, slot, colleur, subject, week or group of one colle.
Admins may edit every colle, other members are limited to their own group.
"""

import sqlite3
import time
from typing import Any

import discord
from discord import app_commands

from cmds._groups import get_group
from cmds._shared import log_command_end, log_command_error, log_command_start
from core.colle import Colle
from core.config import cfg
from core.get_first_group_role import get_first_group_role
from core.perms import is_bot_admin
from db.sql_requests import (
    JOURS,
    get_current_week,
    get_planning_row,
    list_colleurs,
    list_matieres,
    list_planning_rows,
    update_planning_row,
)
from utils.logger import get_logger

logger = get_logger()

_MAX_CHOICES = 25
_NO_GROUP_MSG = "Bruh, j'ai pas trouvé ton groupe, tu es un **INTRUS**, ***BANNISEMMENT EN COURS***!!!"


def _describe(row: sqlite3.Row) -> str:
    colle = Colle(
        colleur_name=row["colleur_name"],
        matiere=row["matiere"],
        jour=JOURS[row["jour_id"]],
        creneau=row["creneau_start"],
        salle=row["salle"],
        is_future=True,
    )
    return f"G{row['groupe']}, semaine {row['semaine']} : {str(colle).strip()}"


def _label(row: sqlite3.Row) -> str:
    label = f"S{row['semaine']} · G{row['groupe']} · {JOURS[row['jour_id']]} {row['creneau_start']}h · {row['matiere']} · {row['colleur_name']} · {row['salle']}"
    return label[:100]


def _search_text(row: sqlite3.Row) -> str:
    jour = JOURS[row["jour_id"]]
    return (
        f"s{row['semaine']} semaine{row['semaine']} g{row['groupe']} groupe{row['groupe']}"
        f" {jour} {jour[:3]} {row['creneau_start']}h {row['creneau_start']}"
        f" {row['matiere']} {row['colleur_name']} {row['salle']}"
    ).lower()


def _colle_choices(current: str) -> list[app_commands.Choice[int]]:
    """Suggest planning rows: current week first, then by week/day/slot/group."""
    tokens = current.lower().split()
    current_week = get_current_week()

    matched = [row for row in list_planning_rows() if all(token in _search_text(row) for token in tokens)]
    matched.sort(key=lambda row: (0 if row["semaine"] == current_week else 1, row["semaine"], row["jour_id"], row["creneau_start"], row["groupe"]))

    return [app_commands.Choice(name=_label(row), value=row["id"]) for row in matched[:_MAX_CHOICES]]


def _build_choices(colleurs: dict[int, str], matieres: dict[int, str]) -> dict[str, list[app_commands.Choice[int]]]:
    choices: dict[str, list[app_commands.Choice[int]]] = {
        "jour": [app_commands.Choice(name=JOURS[jour_id], value=jour_id) for jour_id in sorted(JOURS)],
    }
    if colleurs:
        choices["colleur"] = [app_commands.Choice(name=nom, value=colleur_id) for colleur_id, nom in sorted(colleurs.items(), key=lambda item: item[1].casefold())]
    if matieres:
        choices["matiere"] = [app_commands.Choice(name=nom, value=matiere_id) for matiere_id, nom in sorted(matieres.items(), key=lambda item: item[1].casefold())]
    return choices


def _load_lookups() -> tuple[dict[int, str], dict[int, str]]:
    try:
        return ({row["id"]: row["nom"] for row in list_colleurs()}, {row["id"]: row["nom"] for row in list_matieres()})
    except Exception:
        logger.exception("Failed to load colleurs/matieres for /colle edit")
        return ({}, {})


async def setup(tree: app_commands.CommandTree, bot: Any):
    """Registers the `/colle edit` subcommand."""
    colleurs, matieres = _load_lookups()

    colle_group = get_group(tree, "colle", description="Gestion des colles")

    @colle_group.command(
        name="edit",
        description="Modifie une colle : salle, jour, horaire, colleur, matière, semaine ou groupe",
    )
    @app_commands.describe(
        colle="Colle à modifier",
        salle="Nouvelle salle",
        jour="Nouveau jour",
        heure="Nouvel horaire de début",
        colleur="Nouveau colleur",
        matiere="Nouvelle matière",
        semaine="Nouvelle semaine",
        groupe="Nouveau groupe",
    )
    @app_commands.choices(**_build_choices(colleurs, matieres))
    async def colle_edit(
        interaction: discord.Interaction,
        colle: int,
        salle: str | None = None,
        jour: int | None = None,
        heure: app_commands.Range[int, 0, 23] | None = None,
        colleur: int | None = None,
        matiere: int | None = None,
        semaine: app_commands.Range[int, 1, 52] | None = None,
        groupe: app_commands.Range[int, 1, 14] | None = None,
    ):
        start_time = time.perf_counter()
        log_command_start(logger, "colle-edit", interaction, planning_id=colle)

        try:
            row = get_planning_row(colle)
            if row is None:
                await interaction.response.send_message(f"Colle introuvable (identifiant {colle}).", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="not_found")
                return

            if not is_bot_admin(interaction):
                group_role = get_first_group_role(interaction.user)
                my_group = cfg.GROUPS_CONFIG.role_id_to_number.get(group_role.id) if group_role is not None else None

                if my_group is None:
                    await interaction.response.send_message(_NO_GROUP_MSG, ephemeral=True)
                    log_command_end(logger, "colle-edit", start_time, status="no_group")
                    return

                if row["groupe"] != my_group:
                    await interaction.response.send_message(
                        f"Cette colle est celle du **G{row['groupe']}**, pas du tien. Seul un admin peut la modifier.",
                        ephemeral=True,
                    )
                    log_command_end(logger, "colle-edit", start_time, status="foreign_group")
                    return

                if groupe is not None:
                    await interaction.response.send_message("Seul un admin peut déplacer une colle vers un autre groupe.", ephemeral=True)
                    log_command_end(logger, "colle-edit", start_time, status="group_change_denied")
                    return

            salle_value = salle.strip() if salle is not None else None
            if salle_value == "":
                await interaction.response.send_message("La salle ne peut pas être vide.", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="invalid_salle")
                return

            if colleur is not None and colleur not in colleurs:
                await interaction.response.send_message(f"Colleur introuvable (identifiant {colleur}).", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="unknown_colleur")
                return

            if matiere is not None and matiere not in matieres:
                await interaction.response.send_message(f"Matière introuvable (identifiant {matiere}).", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="unknown_matiere")
                return

            if all(value is None for value in (salle_value, jour, heure, colleur, matiere, semaine, groupe)):
                await interaction.response.send_message(
                    "Donne au moins un champ à modifier : salle, jour, heure, colleur, matière, semaine ou groupe.",
                    ephemeral=True,
                )
                log_command_end(logger, "colle-edit", start_time, status="no_change")
                return

            try:
                updated = update_planning_row(
                    colle,
                    salle=salle_value,
                    jour_id=jour,
                    creneau_start=heure,
                    semaine=semaine,
                    groupe=groupe,
                    colleur_id=colleur,
                    matiere_id=matiere,
                )
            except sqlite3.IntegrityError:
                await interaction.response.send_message(
                    "Impossible de modifier cette colle : ce colleur a déjà une colle sur ce créneau cette semaine-là.",
                    ephemeral=True,
                )
                log_command_end(logger, "colle-edit", start_time, status="conflict")
                return

            if updated != 1:
                await interaction.response.send_message("La colle a entre-temps disparu, réessaie.", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="stale")
                return

            new_row = get_planning_row(colle)
            if new_row is None:
                await interaction.response.send_message("La colle a entre-temps disparu, réessaie.", ephemeral=True)
                log_command_end(logger, "colle-edit", start_time, status="stale")
                return

            await interaction.response.send_message(
                f"✏️ Colle modifiée par {interaction.user.mention} :\n- Avant : {_describe(row)}\n- Après : {_describe(new_row)}",
            )
            log_command_end(logger, "colle-edit", start_time)
        except Exception as exc:
            log_command_error(logger, "colle-edit", exc)
            if not interaction.response.is_done():
                await interaction.response.send_message("Erreur pendant la modification de la colle.", ephemeral=True)
            else:
                await interaction.followup.send("Erreur pendant la modification de la colle.")

    @colle_edit.autocomplete("colle")
    async def colle_autocomplete(interaction: discord.Interaction, current: str):
        try:
            return _colle_choices(current)
        except Exception as exc:
            logger.error("Failed to build the /colle edit autocomplete: %s", exc)
            return []
