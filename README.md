<div align="center">

# MP2I Bot

<div align="center">
<img src="assets/images/bot_profile_picture.png" alt="MP2I Icon" width="160" style="border-radius:24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); margin: 20px 0;" />
</div>

---

**MP2I** is a powerful Discord bot for our MP2I class.

</div>

## Table of contents

- [Features](#-features)
- [Commands](#📜-commands)
- [Quick Start](#-quick-start)
- [Docs](docs/)
- [Dependencies](#-dependencies)
- [Development](#-development)
- [License](#-license)

## Commands

<!-- COMMANDS-START -->
| Command | Description | Permissions |
| :--- | :--- | :--- |
| `/ai` | Configure le comportement du bot IA dans ce salon | Admins |
| `/colle` | Renvoie les colles de la semaine pour l'utilisateur | Admins, Tous les membres |
| `/exec` | Execute la commande SH donnée en argument sur le server ou le bot est host. | Admins |
| `/get-emojis` | Prints all the server's emojis | — |
| `/get-to-work` | Mp tes mate de groupe pour qu'ils se bougent le cul | Admins, Tous les membres |
| `/health` | Statut de santé des sous-systèmes du bot | — |
| `/list-tools` | Liste les outils disponibles pour l'IA | — |
| `/memory-clear` | Efface la mémoire de la conversation actuelle (admin) | — |
| `/memory-delete` | Supprime un échange précis (son auteur ou un admin) | — |
| `/memory-list` | Affiche les derniers échanges en mémoire | — |
| `/model` | Change le modèle d'IA que le bot utilise | Admins |
| `/namestyle` | Change le style d'affichage du bot dans ce serveur | Admins |
| `/ping` | Check bot latency and responsiveness | Admins, Tous les membres |
| `/restart` | Redémarre le bot | Admins |
| `/self-update` | Met à jour le bot depuis le dépôt distant | Admins |
| `/send` | No description provided | Admins |

<!-- COMMANDS-END -->


## Quick Start

### Prerequisites

- Python 3.8+
- Discord Bot Token

### Installation

We use `mise` and `uv` to manage dependencies and environment variables.
See [mise](https://mise.jdx.dev/) and [uv](https://docs.astral.sh/uv/) for installation instructions.

1. **Clone and Setup**

    ```bash
    git clone https://github.com/Elnix90/MP2I.git
    cd MP2I
    python -m venv .venv
    source .venv/bin/activate
    ```

2. **Install Dependencies** (Using `uv` is recommended for speed)

    ```bash
    mise tool install uv
    uv pip install -r requirements.txt
    ```

### Configuration

1. **Create a `.env` file** in the root directory:

<!--ENV-START-->
```env
AI_API_KEY=
BOT_TOKEN=
GUILD_ID=
LATEX_RENDERER_BIN=
LATEX_RENDERER_SCALE=
WEBHOOK_URL=
```
<!--ENV-END-->

1. **Set up your Discord bot**
    - Create a bot on [Discord Developer Portal](https://discord.com/developers/applications)
    - Enable the "Message Content Intent" for the bot to read messages
    - Copy the bot token to your `.env` file

### Running the Bot

```bash
mise run bot
```

## Project Structure

Below is current snapshot of repository. This section is auto-updated by `./lint.sh` on demand.

<!-- TREE-START -->
```
.
├── assets
│   ├── fonts
│   │   ├── IBMPlexMono-Bold.ttf
│   │   ├── IBMPlexMono-Regular.ttf
│   │   ├── NotoSans-BoldItalic.ttf
│   │   ├── NotoSans-Bold.ttf
│   │   ├── NotoSans-Italic.ttf
│   │   ├── NotoSans-Italic-VF.ttf
│   │   ├── NotoSans-Regular.ttf
│   │   └── NotoSans-VF.ttf
│   └── images
│       └── bot_profile_picture.png
├── bot.py
├── cmds
│   ├── ai_channel.py
│   ├── colle.py
│   ├── exec.py
│   ├── get_emojis.py
│   ├── get_to_work.py
│   ├── health.py
│   ├── __init__.py
│   ├── list_tools.py
│   ├── loader.py
│   ├── memory_clear.py
│   ├── memory_delete.py
│   ├── memory_list.py
│   ├── _memory.py
│   ├── model.py
│   ├── namestyle.py
│   ├── ping.py
│   ├── _registry.py
│   ├── restart.py
│   ├── self_update.py
│   ├── send.py
│   └── _shared.py
├── config
│   ├── ai_config.json5
│   ├── ai_conf.py
│   ├── group_ids.json5
│   ├── groups_conf.py
│   ├── logging_config.json5
│   ├── logging_conf.py
│   ├── mcp.json
│   ├── perms_conf.py
│   ├── perms.json5
│   ├── prompts
│   │   └── system.md
│   ├── statuses.json5
│   └── tools
│       ├── discord_search.json
│       ├── image_ocr.json
│       ├── render_visual.json
│       └── safe_eval_math.json
├── core
│   ├── ai
│   │   ├── channels.py
│   │   ├── client.py
│   │   ├── __init__.py
│   │   ├── prompts.py
│   │   └── tools.py
│   ├── colle.py
│   ├── config.py
│   ├── exec_shell_command.py
│   ├── get_first_group_role.py
│   ├── motiver_colle.py
│   └── perms.py
├── db
│   ├── csv_parseur.py
│   ├── generate_colloscope_db.py
│   ├── init
│   │   ├── colleurs.py
│   │   ├── Colloscope MP2I S1.csv
│   │   ├── __init__.py
│   │   ├── jours.py
│   │   ├── rows.py
│   │   └── subjects.py
│   ├── __init__.py
│   ├── settings_store.py
│   ├── sql
│   │   ├── colloscope.sql
│   │   ├── __init__.py
│   │   ├── memory_facts.sql
│   │   ├── memory_schema.sql
│   │   ├── memory_turns.sql
│   │   ├── memory_vec.sql
│   │   └── settings.sql
│   └── sql_requests.py
├── docs
│   ├── handlers.md
│   ├── memory.md
│   └── settings_store.md
├── .github
│   └── workflows
│       ├── pre-commit.yml
│       └── rust.yml
├── .gitignore
├── LICENSE
├── logs
├── main.py
├── managers
│   ├── context.py
│   ├── discord_search.py
│   ├── __init__.py
│   ├── mcp.py
│   ├── memory.py
│   ├── needle.py
│   └── tools
│       ├── discord_search.py
│       ├── image_ocr.py
│       ├── __init__.py
│       ├── render_visual.py
│       └── safe_eval_math.py
├── mise.toml
├── .pre-commit-config.yaml
├── pyproject.toml
├── README.md
├── renderer
│   ├── Cargo.lock
│   ├── Cargo.toml
│   └── src
│       └── main.rs
├── requirements.txt
├── scripts
│   ├── confirm.sh
│   ├── deps.py
│   ├── env.py
│   ├── gen_cmds.py
│   ├── gen_reqs.py
│   ├── lint.sh
│   ├── strip_metadata.sh
│   ├── tree.py
│   └── update_renderer.sh
├── utils
│   ├── console.py
│   ├── debug.py
│   ├── handlers
│   │   ├── codeblock.py
│   │   ├── latex.py
│   │   ├── messages.py
│   │   └── table.py
│   └── logger.py
└── uv.lock

24 directories, 119 files
```
<!-- TREE-END -->

Run `scripts/lint.sh` to format code and regenerate this project tree snapshot. CI runs the same script on every push/PR.

## Dependencies

<!--DEPS-START-->
```markdown
- `Pillow>=10.0.0` - Python Imaging Library (fork) (latest: 12.3.0)
- `aiohttp>=3.9.0` - Async http client/server framework (asyncio) (latest: 3.14.3)
- `asyncio>=3.13.0` - Deprecated backport of asyncio; use the stdlib package instead (latest: 4.0.0)
- `cactus-needle>=1.0.0` - A 14MB foundation tool-calling model for tiny devices: inference, LoRA finetuning, and build. (latest: 3.0.4)
- `cocoindex>=1.0.0` - With CocoIndex, users declare the transformation, CocoIndex creates & maintains an index, and keeps the derived index up to date based on source update, with minimal computation and changes. (latest: 1.0.24)
- `colorama>=0.4.6` - Cross-platform colored terminal text. (latest: 0.4.6)
- `discord.py>=2.3.0` - A Python wrapper for the Discord API (latest: 2.7.1)
- `fastmcp>=2.0.0` - The fast, Pythonic way to build MCP servers and clients. (latest: 4.0.5)
- `json5>=0.9.0` - A Python implementation of the JSON5 data format. (latest: 0.15.0)
- `openai>=1.30.0` - The official Python library for the openai API (latest: 3.17.0)
- `pilmoji>=2.0.0` - Pilmoji is an emoji renderer for Pillow, Python's imaging library. (latest: 2.0.5)
- `pint>=0.24.0` - Physical quantities module (latest: 0.26.1)
- `pytesseract>=0.3.10` - Python-tesseract is a python wrapper for Google's Tesseract-OCR (latest: 0.3.13)
- `python-dotenv>=1.0.0` - Read key-value pairs from a .env file and set them as environment variables (latest: 1.2.3)
- `requests>=2.31.0` - Python HTTP for Humans. (latest: 2.34.2)
- `sqlite-vec>=0.1.0` - latest: 0.1.9
```
<!--DEPS-END-->

## Development

### Linting & CI

- Project provides `lint.sh` at `/scripts/`.
- Run locally before commit:

```bash
chmod +x scripts/lint.sh
scripts/lint.sh
```

- CI: GitHub Actions workflow runs `lint.sh` on `push` and `pull_request` to `master` and feature branches. Fix issues locally and push again.

## License

This project is provided as-is. Please respect Discord's Terms of Service and API usage policies.

## Contributing

Feel free to submit issues and enhancement requests!
