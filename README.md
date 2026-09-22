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

24 directories, 117 files
```
<!-- TREE-END -->

Run `scripts/lint.sh` to format code and regenerate this project tree snapshot. CI runs the same script on every push/PR.

## Dependencies

<!--DEPS-START-->
```markdown
- `aiofile==3.12.3`
- `aiohappyeyeballs==2.7.1`
- `aiohttp==3.14.3`
- `aiosignal==1.4.0`
- `annotated-types==0.8.0`
- `anyio==4.15.1`
- `asyncio==4.0.0`
- `attrs==26.1.0`
- `audioop-lts==0.2.2`
- `authlib==1.8.0`
- `beartype==0.22.9`
- `cachetools==7.2.0`
- `cactus-needle==3.0.2`
- `caio==0.12.4`
- `certifi==2026.7.22`
- `cffi==2.1.1`
- `cfgv==3.5.0`
- `charset-normalizer==3.5.1`
- `click==8.5.0`
- `cocoindex==1.0.23`
- `colorama==0.4.6`
- `cryptography==50.0.1`
- `cyclopts==4.25.3`
- `discord-py==2.7.1`
- `distlib==0.4.3`
- `dnspython==2.8.0`
- `docstring-parser==0.18.0`
- `email-validator==2.3.0`
- `emoji==2.16.0`
- `exceptiongroup==1.3.1`
- `fastmcp==4.0.5`
- `fastmcp-slim==4.0.5`
- `filelock==3.32.7`
- `flexcache==0.3`
- `flexparser==0.4`
- `frozenlist==1.8.0`
- `fsspec==2026.9.0`
- `griffelib==2.3.0`
- `h11==0.16.0`
- `hf-xet==1.6.0`
- `httpcore==1.0.9`
- `httpcore2==2.13.0`
- `httpx==0.28.1`
- `httpx2==2.13.0`
- `huggingface-hub==1.32.0`
- `identify==2.6.19`
- `idna==3.20`
- `isort==9.0.1`
- `jaraco-classes==3.4.0`
- `jaraco-context==6.1.2`
- `jaraco-functools==4.6.0`
- `jeepney==0.9.0`
- `jiter==0.17.0`
- `joserfc==1.7.5`
- `json5==0.15.0`
- `jsonref==1.1.0`
- `jsonschema==4.26.0`
- `jsonschema-path==0.5.0`
- `jsonschema-specifications==2025.9.1`
- `keyring==25.7.0`
- `markdown-it-py==4.2.0`
- `mcp==2.2.0`
- `mcp-types==2.2.0`
- `mdurl==0.1.2`
- `more-itertools==11.1.0`
- `msgspec==0.21.1`
- `multidict==6.9.0`
- `mypy-extensions==1.1.0`
- `nodeenv==1.10.0`
- `numpy==2.5.3`
- `openai==3.16.2`
- `openapi-pydantic==0.5.1`
- `opentelemetry-api==1.44.0`
- `packaging==26.3`
- `pathable==0.6.0`
- `pillow==12.3.0`
- `pilmoji==2.0.5`
- `pint==0.26.1`
- `platformdirs==4.11.11`
- `pre-commit==4.6.2`
- `propcache==0.5.4`
- `psutil==7.2.2`
- `py-key-value-aio==0.4.6`
- `pycparser==3.0`
- `pydantic==2.13.5`
- `pydantic-core==2.46.5`
- `pydantic-settings==2.15.0`
- `pyflakes==3.4.0`
- `pygments==2.21.0`
- `pyjwt==2.14.0`
- `pyperclip==1.11.0`
- `pyright==1.1.414`
- `pytesseract==0.3.13`
- `python-discovery==1.6.1`
- `python-dotenv==1.2.3`
- `python-multipart==0.0.32`
- `pyyaml==6.0.3`
- `referencing==0.37.0`
- `removestar==1.5.2`
- `requests==2.34.2`
- `rich==15.0.0`
- `rich-rst==2.1.0`
- `rpds-py==2026.6.3`
- `ruff==0.16.8`
- `secretstorage==3.5.0`
- `sniffio==1.3.1`
- `sqlite-vec==0.1.9`
- `sse-starlette==3.4.11`
- `starlette==1.6.0`
- `tqdm==4.70.1`
- `truststore==0.10.4`
- `typing-extensions==4.16.0`
- `typing-inspection==0.4.4`
- `uncalled-for==0.4.0`
- `urllib3==2.8.0`
- `uvicorn==0.53.0`
- `virtualenv==21.7.16`
- `watchdog==6.0.0`
- `watchfiles==1.2.0`
- `websockets==17.1`
- `yarl==1.25.1`
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
