"""Helpers for sending long or formatted Discord messages."""

import re
from typing import TYPE_CHECKING, cast

import discord

from utils.handlers.codeblock import send_code_block_with_return
from utils.handlers.latex import LATEX_TO_EMOJI, detect_latex
from utils.handlers.table import TABLE_IMAGE_PLACEHOLDER, detect_and_convert_tables
from utils.logger import get_logger

if TYPE_CHECKING:
    from utils.debug import DebugWriter

logger = get_logger()


class MessageSender:
    def __init__(
        self,
        channel: discord.abc.Messageable,
        bot: discord.Client | None = None,
        max_length: int = 2000,
        *,
        debug: "DebugWriter | None" = None,
    ):
        self.channel = channel
        self.bot = bot
        self.max_length = max_length
        self.debug = debug
        self._debug_header_sent = False

    def _get_target_channel(self) -> discord.abc.Messageable:
        if self.bot:
            channel_id = getattr(self.channel, "id", None)
            if isinstance(channel_id, int):
                return cast(
                    discord.abc.Messageable,
                    self.bot.get_channel(channel_id) or self.channel,
                )
        return self.channel

    async def send_text_chunks(self, text: str) -> discord.Message | None:
        if not text.strip():
            return None
        if self.debug:
            self.debug.add_content(text)
        target = self._get_target_channel()
        lines = text.splitlines(keepends=True)
        current_message = ""
        last_message = None
        for line in lines:
            if len(line) > self.max_length:
                if current_message:
                    last_message = await target.send(current_message.rstrip())
                    current_message = ""
                for i in range(0, len(line), self.max_length):
                    chunk = line[i : i + self.max_length]
                    last_message = await target.send(chunk.rstrip())
            elif len(current_message) + len(line) > self.max_length:
                if current_message:
                    last_message = await target.send(current_message.rstrip())
                current_message = line
            else:
                current_message += line
        if current_message.strip():
            last_message = await target.send(current_message.rstrip())
        return last_message

    async def send_latex_image(self, latex_match: str) -> discord.Message | None:
        from utils.handlers.latex import convert_latex_to_png

        latex = self._clean_latex(latex_match)
        result, success = convert_latex_to_png(latex)
        target = self._get_target_channel()
        if success:
            if isinstance(result, str):
                return await target.send(result)
            if self.debug:
                result.seek(0)
                rel_path = self.debug.save_image(result, f"latex_{self.debug._image_counter}.png")
                self.debug.add_content(f"![latex]({rel_path})")
                result.seek(0)
            file = discord.File(result, filename="formula.png")
            return await target.send(file=file)
        latex_display = latex[:100] + "..." if len(latex) > 100 else latex
        return await target.send(f"Failed to render LaTeX: {latex_display}")

    def _clean_latex(self, latex: str) -> str:
        latex = latex.strip()
        if latex.startswith("```") and latex.endswith("```"):
            lines = latex.split("\n")
            if len(lines) >= 3 and lines[-1] == "```":
                latex = "\n".join(lines[1:-1])
        if latex.startswith("$") and latex.endswith("$"):
            latex = latex[1:-1]
        if latex.startswith(r"\[") and latex.endswith(r"\]"):
            latex = latex[2:-2]
        if latex.startswith(r"\(") and latex.endswith(r"\)"):
            latex = latex[2:-2]
        return latex

    async def send_text_with_latex(self, text: str) -> discord.Message | None:
        matches = detect_latex(text)
        if not matches:
            return await self.send_text_chunks(text)
        current_text = ""
        last_end = 0
        last_message = None
        for match in matches:
            start = text.find(match, last_end)
            if start == -1:
                continue
            current_text += text[last_end:start]
            latex = self._clean_latex(match)
            if latex in LATEX_TO_EMOJI:
                current_text += LATEX_TO_EMOJI[latex]
            else:
                if current_text:
                    last_message = await self.send_text_chunks(current_text)
                    current_text = ""
                last_message = await self.send_latex_image(match)
            last_end = start + len(match)
        current_text += text[last_end:]
        if current_text:
            last_message = await self.send_text_chunks(current_text)
        return last_message

    async def process_and_send(self, response: str) -> tuple[discord.Message | None, list[dict]]:
        response, table_images, table_data = detect_and_convert_tables(response)

        debug_prefix = ""
        if self.debug and not self._debug_header_sent:
            debug_prefix = self.debug.debug_header()
            self._debug_header_sent = True

        placeholder_escaped = re.escape(TABLE_IMAGE_PLACEHOLDER)
        pattern = re.compile(f"({placeholder_escaped}_\\d+__)|(```[\\s\\S]*?```)")
        parts = [p for p in pattern.split(response) if p is not None]
        target = self._get_target_channel()
        last_message = None
        first_text = True
        for part in parts:
            if not part:
                continue
            if part.startswith(TABLE_IMAGE_PLACEHOLDER) and part.endswith("__"):
                try:
                    idx_str = part[len(TABLE_IMAGE_PLACEHOLDER) + 1 : -2]
                    idx = int(idx_str)
                    if idx < len(table_images):
                        img_buffer = table_images[idx]
                        img_buffer.seek(0)
                        if self.debug:
                            img_buffer.seek(0)
                            self.debug.save_image(img_buffer, f"table_{idx}.png")
                            img_buffer.seek(0)
                        file = discord.File(fp=img_buffer, filename=f"table_{idx}.png")
                        last_message = await target.send(file=file)
                        if self.debug:
                            self.debug.add_content(f"![table_{idx}](images/table_{idx}.png)")
                    else:
                        last_message = await self.send_text_with_latex(part)
                except Exception as exc:
                    logger.error("Failed to send table message: %s", exc)
                    last_message = await self.send_text_with_latex(part)
            elif part.startswith("```") and part.endswith("```"):
                if TABLE_IMAGE_PLACEHOLDER not in part:
                    if first_text and debug_prefix:
                        part = debug_prefix + part
                        first_text = False
                    last_message = await send_code_block_with_return(target, part, self.max_length, bot=self.bot)
            else:
                if first_text and debug_prefix:
                    part = debug_prefix + part
                    first_text = False
                last_message = await self.send_text_with_latex(part)
        return last_message, table_data
