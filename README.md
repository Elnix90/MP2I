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
| `/ai` | Configure le mode IA d'un salon (admin) | Admins |
| `/colle` | Renvoie les colles de la semaine pour l'utilisateur | Admins, Tous les membres |
| `/exec` | Execute la commande SH donnée en argument sur le server ou le bot est host. | Admins |
| `/get-to-work` | Mp tes mate de groupe pour qu'ils se bougent le cul | Admins, Tous les membres |
| `/health` | Statut de santé des sous-systèmes du bot | — |
| `/list-tools` | Liste les outils disponibles pour l'IA | — |
| `/memory-clear` | Efface la mémoire de la conversation actuelle (admin) | — |
| `/memory-delete` | Supprime un échange précis (son auteur ou un admin) | — |
| `/memory-list` | Affiche les derniers échanges en mémoire | — |
| `/model` | Change le modèle d'IA que le bot utilise | Admins |
| `/ping` | Check bot latency and responsiveness | Admins, Tous les membres |
| `/restart` | Redémarre le bot (réservé aux admins) | Admins |
| `/self-update` | Met à jour le bot depuis le dépôt distant | Admins |

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
BOT_TOKEN=
GUILD_ID=
WEBHOOK_URL=
AI_API_KEY=
PARALLEL_API_KEY=
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
│   │   ├── NotoSans-BoldItalic.ttf
│   │   ├── NotoSans-Bold.ttf
│   │   ├── NotoSans-Italic.ttf
│   │   └── NotoSans-Regular.ttf
│   └── images
│       └── bot_profile_picture.png
├── bot.py
├── cmds
│   ├── ai_channel.py
│   ├── colle.py
│   ├── exec.py
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
│   ├── ping.py
│   ├── _registry.py
│   ├── restart.py
│   ├── self_update.py
│   └── _shared.py
├── config
│   ├── ai_config.json5
│   ├── ai_conf.py
│   ├── logging_config.json5
│   ├── logging_conf.py
│   ├── mcp.json
│   ├── perms_conf.py
│   ├── perms.json5
│   ├── prompts
│   │   └── system.md
│   ├── statuses.json5
│   └── tools
│       ├── image_ocr.json
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
│   ├── perms.py
│   └── roles_ids.py
├── db
│   ├── colloscope.db
│   ├── cvs_parseur.py
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
│   │   ├── colles.sql
│   │   ├── colleurs_insert.sql
│   │   ├── colloscope_schema.sql
│   │   ├── __init__.py
│   │   ├── matieres_insert.sql
│   │   ├── planning_insert.sql
│   │   ├── settings_get.sql
│   │   ├── settings_schema.sql
│   │   └── settings_upsert.sql
│   └── sql_requests.py
├── debug
│   └── messages
├── docs
│   └── settings_store.md
├── .github
│   └── workflows
│       └── pre-commit.yml
├── .gitignore
├── LICENSE
├── main.py
├── managers
│   ├── context.py
│   ├── __init__.py
│   ├── mcp.py
│   ├── memory.py
│   ├── needle.py
│   └── tools
│       ├── image_ocr.py
│       ├── __init__.py
│       └── safe_eval_math.py
├── mise.toml
├── .pre-commit-config.yaml
├── pyproject.toml
├── README.md
├── requirements.txt
├── scripts
│   ├── deps.py
│   ├── env.py
│   ├── gen_cmds.py
│   ├── lint.sh
│   ├── strip_metadata.sh
│   └── tree.py
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

23 directories, 100 files
```
<!-- TREE-END -->

Run `./lint.sh` to format code and regenerate this project tree snapshot. CI runs the same script on every push/PR.

## Dependencies

<!--DEPS-START-->
```markdown
- `discord.py` - A Python wrapper for the Discord API (latest: 2.7.1)
- `python-dotenv` - Read key-value pairs from a .env file and set them as environment variables (latest: 1.2.3)
- `colorama` - Cross-platform colored terminal text. (latest: 0.4.6)
- `requests` - Python HTTP for Humans. (latest: 2.34.2)
- `openai` - The official Python library for the openai API (latest: 3.16.2)
- `json5` - A Python implementation of the JSON5 data format. (latest: 0.15.0)
- `aiohttp` - Async http client/server framework (asyncio) (latest: 3.14.3)
- `Pillow` - Python Imaging Library (fork) (latest: 12.3.0)
- `pilmoji` - Pilmoji is an emoji renderer for Pillow, Python's imaging library. (latest: 2.0.5)
- `cairosvg` - A Simple SVG Converter based on Cairo (latest: 2.9.1)
- `pytesseract` - Python-tesseract is a python wrapper for Google's Tesseract-OCR (latest: 0.3.13)
- `fastmcp` - The fast, Pythonic way to build MCP servers and clients. (latest: 4.0.5)
- `cocoindex` - With CocoIndex, users declare the transformation, CocoIndex creates & maintains an index, and keeps the derived index up to date based on source update, with minimal computation and changes. (latest: 1.0.23)
- `pint` - Physical quantities module (latest: 0.26.1)
- `cactus-needle` - A 14MB foundation tool-calling model for tiny devices: inference, LoRA finetuning, and build. (latest: 3.0.2)
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
