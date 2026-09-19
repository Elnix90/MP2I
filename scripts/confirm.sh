#!/usr/bin/env bash
# confirm.sh — Ask for confirmation.
# Usage: source scripts/confirm.sh; confirm "Are you sure?" && echo "yes"

confirm() {
    local prompt="${1:-Confirmer ?}"
    printf "%s (y/N) " "$prompt"
    read -r confirm_reply
    [ "$confirm_reply" = "y" ]
}
