"""Debug mode writer: saves AI responses as markdown with embedded images.

When ``DEBUG_MODE`` is enabled, each AI response is saved to
``debug/messages/{turn_id}/message.md`` with a ``images/`` subdirectory
containing any table or LaTeX images that were sent.
"""

import io
import uuid
from datetime import UTC, datetime

from core.config import BASE_DIR
from utils.logger import get_logger

logger = get_logger()

DEBUG_MESSAGES_DIR = BASE_DIR / "debug" / "messages"
DEBUG_MESSAGES_DIR.mkdir(parents=True, exist_ok=True)


class DebugWriter:
    """Accumulates message content and images, then writes a debug markdown file."""

    def __init__(
        self,
        turn_id: str,
        channel: object,
        user: object,
    ) -> None:
        self.turn_id = turn_id
        self.channel = channel
        self.user = user
        self.debug_dir = DEBUG_MESSAGES_DIR / turn_id
        self.images_dir = self.debug_dir / "images"
        self.content_parts: list[str] = []
        self._image_counter = 0

        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)

    def save_image(self, buffer: io.BytesIO, filename: str) -> str:
        """Save an image buffer to disk, return relative path for markdown."""
        self._image_counter += 1
        path = self.images_dir / filename
        buffer.seek(0)
        path.write_bytes(buffer.read())
        return f"images/{filename}"

    def add_content(self, text: str) -> None:
        """Append a text chunk to the markdown body."""
        if text.strip():
            self.content_parts.append(text)

    def debug_header(self) -> str:
        """Return a short metadata line to prepend to Discord messages."""
        channel_name = getattr(self.channel, "name", None) or getattr(self.channel, "id", "?")
        user_name = getattr(self.user, "display_name", None) or getattr(self.user, "name", "?")
        return f"\U0001f4e1 **debug** `{channel_name}` | `{user_name}` | `{self.turn_id[:8]}`\n"

    def save(self, user_message: str) -> None:
        """Write the complete debug markdown file."""
        channel_name = getattr(self.channel, "name", None) or str(getattr(self.channel, "id", "?"))
        channel_id = getattr(self.channel, "id", "?")
        user_name = getattr(self.user, "display_name", None) or getattr(self.user, "name", "?")
        user_id = getattr(self.user, "id", "?")

        ts = datetime.now(UTC).isoformat()

        body = "\n\n".join(self.content_parts)

        md = f"""---
turn_id: {self.turn_id}
channel_id: {channel_id}
channel_name: {channel_name}
user_id: {user_id}
user_name: {user_name}
timestamp: {ts}
---

## User

{user_message}

## Bot

{body}
"""
        out = self.debug_dir / "message.md"
        out.write_text(md, encoding="utf-8")
        logger.debug("Debug: saved %s (%d bytes, %d images)", out, len(md), self._image_counter)


def new_turn_id() -> str:
    return uuid.uuid4().hex
