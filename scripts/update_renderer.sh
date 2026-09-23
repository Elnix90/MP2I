#!/usr/bin/env bash
# Télécharge le binaire précompilé mp2i-render (release roulante "prebuilt")
# et le pose dans renderer/target/release/.
# Utilisé par `mise run renderer-install` et par la commande /self-update.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="https://github.com/Elnix90/MP2I/releases/download/prebuilt/mp2i-render-linux-x86_64.tar.gz"
DEST="${RENDERER_BIN_DIR:-$REPO_ROOT/renderer/target/release}"

mkdir -p "$DEST"
curl -fsSL -o /tmp/mp2i-render.tar.gz "$URL"
tar -xzf /tmp/mp2i-render.tar.gz -C "$DEST"
chmod +x "$DEST/mp2i-render"
"$DEST/mp2i-render" --help >/dev/null
echo "mp2i-render updated -> $DEST/mp2i-render"
