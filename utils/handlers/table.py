"""Render markdown tables as images for Discord messages."""

import io
import re
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from core.config import BASE_DIR
from utils.logger import get_logger

logger = get_logger()

URL_REGEX = r"\[([^\]]+)\]\((https?://[^\s\)]+)\)|(https?://[^\s\)]+)"
TABLE_IMAGE_PLACEHOLDER = "__TABLE_IMG"
EMOJI_BUFFER = 12
COLUMN_MAX_WIDTH = 1200
FONT_DIR = BASE_DIR / "assets" / "fonts"


def _extract_links_and_sanitize(text: str, current_links: list[str]) -> tuple[str, list[str]]:
    def replacer(match: re.Match[str]) -> str:
        _label, url_md, url_plain = match.groups()
        url = url_md or url_plain
        if url in current_links:
            idx = current_links.index(url) + 1
        else:
            current_links.append(url)
            idx = len(current_links)

        domain = urlparse(url).netloc
        domain = domain.removeprefix("www.")
        return f"[{idx}] ({domain})"

    sanitized_text = re.sub(URL_REGEX, replacer, text)
    return sanitized_text, current_links


def _get_font(size: int, bold: bool = False, italic: bool = False):
    try:
        if bold and italic:
            path = FONT_DIR / "NotoSans-BoldItalic.ttf"
        elif bold:
            path = FONT_DIR / "NotoSans-Bold.ttf"
        elif italic:
            path = FONT_DIR / "NotoSans-Italic.ttf"
        else:
            path = FONT_DIR / "NotoSans-Regular.ttf"
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()


def _calc_col_widths(
    headers: list[str],
    rows: list[list[str]],
    font: ImageFont.FreeTypeFont,
    padding: int,
) -> list[int]:
    img = Image.new("RGB", (1, 1))
    widths = []
    with Pilmoji(img) as pilmoji:
        for i, header in enumerate(headers):
            max_w = pilmoji.draw.textlength(str(header), font=font) + padding * 2
            for row in rows:
                if i < len(row):
                    cell_text = str(row[i])
                    for line in cell_text.split("\n"):
                        raw_w = pilmoji.draw.textlength(line, font=font)
                        if any(ord(c) > 0xFFFF for c in line):
                            raw_w += EMOJI_BUFFER
                        max_w = max(max_w, raw_w + padding * 2)
            widths.append(int(min(max_w, COLUMN_MAX_WIDTH)))
    return widths


def _wrap_text(text: str, max_width: int, font: ImageFont.FreeTypeFont) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        w = draw.textlength(test_line, font=font)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _render_table_image(headers: list[str], rows: list[list[str]], alignments: list[str]) -> tuple[io.BytesIO, list[str]]:
    all_links: list[str] = []
    sanitized_headers = []
    for h in headers:
        text, all_links = _extract_links_and_sanitize(h, all_links)
        sanitized_headers.append(text)

    sanitized_rows = []
    for row in rows:
        san_row = []
        for cell in row:
            text, all_links = _extract_links_and_sanitize(str(cell), all_links)
            san_row.append(text)
        sanitized_rows.append(san_row)

    font_size = 32
    fonts = {
        "reg": _get_font(font_size),
        "bold": _get_font(font_size, bold=True),
        "header": _get_font(font_size + 4, bold=True),
        "line_height": font_size + 10,
    }
    colors = {
        "bg": (7, 7, 9),
        "header_bg": (28, 28, 32),
        "row_bg": (7, 7, 9),
        "row_bg_alt": (28, 28, 32),
        "border": (60, 60, 65),
        "text": (255, 255, 255),
    }

    padding, header_height, min_row_h = 24, 80, 60
    col_widths = _calc_col_widths(sanitized_headers, sanitized_rows, fonts["reg"], padding)

    processed_rows = []
    for row in sanitized_rows:
        row_content = []
        max_h = min_row_h
        for i, cell in enumerate(row):
            wrapped = _wrap_text(cell, col_widths[i] - padding * 2, fonts["reg"])
            row_content.append(wrapped)
            max_h = max(max_h, len(wrapped) * fonts["line_height"] + padding)
        processed_rows.append((row_content, max_h))

    total_w = sum(col_widths) + len(col_widths) + 1
    total_h = header_height + sum(h for _, h in processed_rows) + len(processed_rows) + 1

    img = Image.new("RGB", (total_w, total_h), colors["bg"])
    draw = ImageDraw.Draw(img)
    with Pilmoji(img) as pilmoji:
        x = 0
        for h_text, w, al in zip(sanitized_headers, col_widths, alignments):
            draw.rectangle(
                [x, 0, x + w, header_height],
                fill=colors["header_bg"],
                outline=colors["border"],
            )
            pilmoji.text(
                (x + padding, header_height // 2),
                h_text,
                fill=colors["text"],
                font=fonts["header"],
                anchor="lm",
            )
            x += w + 1

        y = header_height + 1
        for idx, (content, h_row) in enumerate(processed_rows):
            x = 0
            bg = colors["row_bg_alt"] if idx % 2 else colors["row_bg"]
            for cell_lines, w, al in zip(content, col_widths, alignments):
                draw.rectangle([x, y, x + w, y + h_row], fill=bg, outline=colors["border"])
                for line_idx, line in enumerate(cell_lines):
                    line_y = y + padding // 2 + line_idx * fonts["line_height"] + fonts["line_height"] // 2
                    pilmoji.text(
                        (x + padding, line_y),
                        line,
                        fill=colors["text"],
                        font=fonts["reg"],
                        anchor="lm",
                    )
                x += w + 1
            y += h_row + 1

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, all_links


def _is_separator_line(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-\:\|]*\|$", line.strip()))


def _parse_table_lines(lines: list[str]) -> tuple[list[str], list[list[str]], list[str]] | None:
    headers = [p.strip() for p in lines[0].strip()[1:-1].split("|")]
    if not headers:
        return None

    aligns: list[str] = []
    start_row = 1
    if len(lines) > 1 and _is_separator_line(lines[1]):
        for p in lines[1].strip()[1:-1].split("|"):
            p = p.strip()
            if p.startswith(":") and p.endswith(":"):
                aligns.append("center")
            elif p.endswith(":"):
                aligns.append("right")
            else:
                aligns.append("left")
        start_row = 2

    rows = []
    for i in range(start_row, len(lines)):
        row_raw = lines[i].strip()
        row_raw = row_raw.removeprefix("|").removesuffix("|")
        cells = [c.strip() for c in row_raw.split("|")]
        rows.append(cells[: len(headers)] + [""] * (len(headers) - len(cells)))

    return headers, rows, aligns or ["left"] * len(headers)


def detect_and_convert_tables(text: str) -> tuple[str, list[io.BytesIO], list[dict]]:
    table_images: list[io.BytesIO] = []
    table_data_list: list[dict] = []

    code_block_pattern = re.compile(r"```(?:markdown|md)\n((?:\|.*\|(?:\n|$))+)```", re.MULTILINE)

    def replace_table(lines: list[str]) -> str:
        if len(lines) < 2:
            return "\n".join(lines)
        parsed = _parse_table_lines(lines)
        if parsed is None:
            return "\n".join(lines)

        headers, rows, aligns = parsed
        try:
            buf, links = _render_table_image(headers, rows, aligns)
            table_images.append(buf)
            idx = len(table_images) - 1
            table_data_list.append({"id": idx, "headers": headers, "rows": rows, "links": links})
            return f"__TABLE_IMG_{idx}__"
        except Exception as exc:
            logger.error("Table render error: %s", exc)
            return "\n".join(lines)

    def replace_fenced(match: re.Match[str]) -> str:
        lines = [row_line for row_line in match.group(1).strip().split("\n") if row_line.strip()]
        return replace_table(lines)

    new_text = code_block_pattern.sub(replace_fenced, text)

    # Convert standalone (unfenced) markdown tables, skipping code blocks.
    def convert_raw_tables(segment: str) -> str:
        lines = segment.split("\n")
        out: list[str] = []
        i = 0
        n = len(lines)
        while i < n:
            if lines[i].lstrip().startswith("|"):
                # Collect consecutive pipe lines
                block = [lines[i]]
                j = i + 1
                while j < n and lines[j].lstrip().startswith("|"):
                    block.append(lines[j])
                    j += 1
                # Require at least 2 pipe lines to be a table
                if len(block) >= 2:
                    out.append(replace_table(block))
                else:
                    out.extend(block)
                i = j
                continue
            out.append(lines[i])
            i += 1
        return "\n".join(out)

    parts = re.split(r"(```[\s\S]*?```)", new_text)
    new_text = "".join(convert_raw_tables(part) if i % 2 == 0 else part for i, part in enumerate(parts))

    return new_text, table_images, table_data_list
