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
    """Return the persisted channel -> mode mapping.

    Falls back to ``cfg.AI_ALLOWED_CHANNELS`` (treated as normal-mode) when
    the store is empty, to stay compatible with the historic config list.

    Returns
    -------
    dict[int, str]
        Mapping of channel id to channel mode.
    """
    stored = get_setting(STORE_KEY)
    if isinstance(stored, dict) and stored:
        try:
            return {int(k): str(v) for k, v in stored.items()}
        except (TypeError, ValueError):
            logger.warning("Invalid ai.channels store, using config default")

    return {int(c): "normal" for c in cfg.AI_ALLOWED_CHANNELS}


def save_channel_modes(modes: dict[int, str]) -> None:
    """Persist the full channel -> mode mapping."""
    set_setting(STORE_KEY, {int(k): str(v) for k, v in modes.items()})


def get_channel_mode(channel_id: int | None) -> str | None:
    """Return the mode of a channel, or None when it is not authorized.

    Parameters
    ----------
    channel_id : int | None
        Channel id to inspect.

    Returns
    -------
    str | None
        ``"normal"``, ``"thread"``, or None when the channel is not configured.
    """
    if channel_id is None:
        return None
    return load_channel_modes().get(int(channel_id))


def set_channel_mode(channel_id: int, mode: str) -> None:
    """Set the mode of a channel (persisted).

    Parameters
    ----------
    channel_id : int
        Channel id to configure.
    mode : str
        One of ``CHANNEL_MODES``.
    """
    if mode not in CHANNEL_MODES:
        raise ValueError(f"Unknown channel mode: {mode}")
    modes = load_channel_modes()
    modes[int(channel_id)] = mode
    save_channel_modes(modes)


def remove_channel(channel_id: int) -> bool:
    """Remove a channel from the configured set (persisted).

    Returns
    -------
    bool
        True if the channel was configured and was removed.
    """
    modes = load_channel_modes()
    if int(channel_id) not in modes:
        return False
    del modes[int(channel_id)]
    save_channel_modes(modes)
    return True


def is_allowed_channel(channel_id: int | None) -> bool:
    """Backward-compatible predicate: True when the channel has a mode."""
    return get_channel_mode(channel_id) is not None
