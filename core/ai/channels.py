"""AI channel configuration helpers.

Each channel is in one of three states, stored in the persistent settings
store as ``ai.channels = {channel_id: mode}``:

- absent: the bot ignores the channel
- ``"normal"``: the bot replies in-channel on mention, with channel-scoped memory
- ``"thread"``: each mention starts a thread, with per-thread memory
"""

from core.config import cfg
from db.settings_store import get_setting, set_setting
from utils.logger import get_logger

logger = get_logger()

STORE_KEY = "ai.channels"

CHANNEL_MODES = ("normal", "thread")


def load_channel_modes() -> dict[int, str]:
    stored = get_setting(STORE_KEY)
    if isinstance(stored, dict) and stored:
        try:
            return {int(k): str(v) for k, v in stored.items()}
        except (TypeError, ValueError):
            logger.warning("Invalid ai.channels store, using config default")

    return {int(c): "normal" for c in cfg.AI_ALLOWED_CHANNELS}


def save_channel_modes(modes: dict[int, str]) -> None:
    set_setting(STORE_KEY, {int(k): str(v) for k, v in modes.items()})


def get_channel_mode(channel_id: int | None) -> str | None:
    if channel_id is None:
        return None
    return load_channel_modes().get(int(channel_id))


def set_channel_mode(channel_id: int, mode: str) -> None:
    if mode not in CHANNEL_MODES:
        raise ValueError(f"Unknown channel mode: {mode}")
    modes = load_channel_modes()
    modes[int(channel_id)] = mode
    save_channel_modes(modes)


def remove_channel(channel_id: int) -> bool:
    modes = load_channel_modes()
    if int(channel_id) not in modes:
        return False
    del modes[int(channel_id)]
    save_channel_modes(modes)
    return True


def is_allowed_channel(channel_id: int | None) -> bool:
    return get_channel_mode(channel_id) is not None
