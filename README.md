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
| `/health` | Show runtime health for bot subsystems |
| `/ping` | Check bot latency and responsiveness |

<!-- COMMANDS-END -->


## Quick Start

### Prerequisites

- Python 3.8+
- Discord Bot Token
- 
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

## Deployment

EvilGPT is designed for simple and reliable deployment on Linux servers.

### 1. Automated SSH Deployment

A powerful [`deploy.sh`](deploy.sh) script is provided to automate the entire process (transfer, dependencies, service restart).

1. **Prerequisites**: Install `sshpass` locally: `sudo apt install sshpass`.
2. **Setup**: Configure your server details in the `.env` file (see [Configuration](#configuration)).
3. **Execute**:

    ```bash
    chmod +x deploy.sh
    ./deploy.sh
    ```

## Project Structure

Below is current snapshot of repository. This section is auto-updated by `./lint.sh` on demand.

<!-- TREE-START -->
```
.
├── assets
│   └── images
│       ├── evilgpt.png
│       ├── evilgpt.svg
│       └── MPI2-server-icon.png
├── bot.py
├── cmds
│   ├── health.py
│   ├── __init__.py
│   ├── loader.py
│   ├── ping.py
│   ├── _registry.py
│   └── _shared.py
├── config.toml
├── core
│   └── config.py
├── .github
│   └── workflows
│       └── pre-commit.yml
├── .gitignore
├── LICENSE
├── lint.sh
├── main.py
├── mise.toml
├── README.md
├── requirements.txt
├── scripts
│   ├── generate_docs.py
│   └── strip_metadata.sh
└── utils
    └── logger.py

9 directories, 23 files
```
<!-- TREE-END -->

Run `./lint.sh` to format code and regenerate this project tree snapshot. CI runs the same script on every push/PR.

## Dependencies

<!--DEPS-START-->
```markdown
- `discord.py==2.7.1` - A Python wrapper for the Discord API (latest: 2.7.1)
- `python-dotenv==1.2.2` - Read key-value pairs from a .env file and set them as environment variables (latest: 1.2.3)
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
