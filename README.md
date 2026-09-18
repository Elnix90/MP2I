<div align="center">

# MP2I Bot

<div align="center">
<img src="assets/images/MPI2-server-icon.png" alt="MP2I Icon" width="160" style="border-radius:24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); margin: 20px 0;" />
</div>

---

**MP2I** is a powerful Discord bot for our MP2I class.

</div>

## Table of contents

- [Features](#-features)
- [Commands](#📜-commands)
- [Quick Start](#-quick-start)
- [Dependencies](#-dependencies)
- [Development](#-development)
- [License](#-license)

## Commands

<!-- COMMANDS-START -->
| Command | Description |
| :--- | :--- |
| `/ai-allow` | Autorise le bot IA à répondre dans ce salon (réservé aux admins) |
| `/ai-deny` | Empêche le bot IA de répondre dans ce salon (réservé aux admins) |
| `/colle` | Renvoie les colles de la semaine pour l'utilisateur |
| `/exec` | Execute la commande SH donnée en argument sur le server ou le bot est host. (réservé aux admins) |
| `/get-to-work` | Mp tes mate de groupe pour qu'ils se bougent le cul |
| `/ping` | Check bot latency and responsiveness |
| `/restart` | Redémarre le bot (réservé aux admins) |
| `/self-update` | Automatiquement met à jour le bot depuis son serveur distant |

<!-- COMMANDS-END -->


## Quick Start

### Prerequisites

- Python 3.8+
- Discord Bot Token

### Installation

1. **Clone and Setup**

    ```bash
    git clone https://github.com/Elnix90/MP2I.git
    cd MP2I
    python -m venv .venv
    source .venv/bin/activate
    ```

2. **Install Dependencies** (Using `uv` is recommended for speed)

    ```bash
    pip install uv
    uv pip install -r requirements.txt
    ```

### Configuration

1. **Create a `.env` file** in the root directory:

<!--ENV-START-->
```env
BOT_TOKEN=
GUILD_ID=
BOT_ID=
WEBHOOK_URL=
AI_API_KEY=
```
<!--ENV-END-->

1. **Set up your Discord bot**
    - Create a bot on [Discord Developer Portal](https://discord.com/developers/applications)
    - Enable the "Message Content Intent" for the bot to read messages
    - Copy the bot token to your `.env` file

### Running the Bot

```bash
python main.py
```

## Project Structure

Below is current snapshot of repository. This section is auto-updated by `./lint.sh` on demand.

<!-- TREE-START -->
```
.
├── assets
│   └── images
│       └── MPI2-server-icon.png
├── bot.py
├── cmds
│   ├── ai_channel.py
│   ├── colle.py
│   ├── exec.py
│   ├── get_to_work.py
│   ├── __init__.py
│   ├── loader.py
│   ├── ping.py
│   ├── _registry.py
│   ├── restart.py
│   ├── self_update.py
│   └── _shared.py
├── config.toml
├── core
│   ├── ai.py
│   ├── colle.py
│   ├── config.py
│   ├── exec_shell_command.py
│   ├── get_first_group_role.py
│   ├── is_admin.py
│   ├── motiver_colle.py
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
│   └── sql_requests.py
├── .github
│   └── workflows
│       └── pre-commit.yml
├── .gitignore
├── LICENSE
├── main.py
├── mise.toml
├── .pre-commit-config.yaml
├── pyproject.toml
├── README.md
├── requirements.txt
├── scripts
│   ├── cmds.py
│   ├── deps.py
│   ├── env.py
│   ├── lint.sh
│   ├── strip_metadata.sh
│   └── tree.py
└── utils
    ├── console.py
    ├── handlers
    └── logger.py

12 directories, 50 files
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
- `aiohttp` - Async http client/server framework (asyncio) (latest: 3.14.3)
- `httpx` - The next generation HTTP client. (latest: 0.28.1)
- `starlette` - The little ASGI library that shines. (latest: 1.6.0)
```
<!--DEPS-END-->

## Development

### Linting & CI

- Project provides `lint.sh` at repo root.
- Run locally before commit:

```bash
./lint.sh
```

- CI: GitHub Actions workflow runs `lint.sh` on `push` and `pull_request` to `master` and feature branches. Fix issues locally and push again.

## License

This project is provided as-is. Please respect Discord's Terms of Service and API usage policies.

## Contributing

Feel free to submit issues and enhancement requests!
