"""Render markdown tables as images for Discord messages.

Tables render with proper inline markdown — ``**bold**``, ``*italic*``,
``\\`code\\``` spans use distinct fonts. Code spans use IBM Plex Mono;
the rest uses Noto Sans (variable axis weight via Pillow).
"""

import io
import re
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji

from core.config import BASE_DIR
from utils.logger import get_logger

logger = get_logger()

URL_REGEX = r"\[([^\]]+)\]\((https?://[^\s\)]+)\)|(https?://[^\s\)]+)"
TABLE_IMAGE_PLACEHOLDER = "__TABLE_IMG"
COLUMN_MAX_WIDTH = 1200
FONT_DIR = BASE_DIR / "assets" / "fonts"

# Variable-font weight axis values
WGHT_REGULAR = 400
WGHT_BOLD = 700

# Inline-formatting parser
_INLINE_PATTERN = re.compile(r"(`[^`]+`|\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|\*[^*]+?\*|__[^_]+?__)")

# Style constants
FONT_SIZE = 28
HEADER_FONT_SIZE = 32
PADDING = 24
HEADER_HEIGHT = 80
MIN_ROW_HEIGHT = 60
LINE_HEIGHT_RATIO = 1.35

PALETTE = {
    "bg": (7, 7, 9),
    "header_bg": (28, 28, 32),
    "row_bg": (7, 7, 9),
    "row_bg_alt": (28, 28, 32),
    "border": (60, 60, 65),
    "text": (255, 255, 255),
    "header_text": (255, 255, 255),
    "code_bg": (39, 39, 37),
    "code_text": (235, 235, 232),
}


# =============================================================================
# Font loading
# =============================================================================


def _load_variation(path: Path, size: int, wght: int):
    """Load a variable TTF and apply the wght axis."""
    try:
        font = ImageFont.truetype(str(path), size)
        try:
            font.set_variation_by_axes([wght])
        except (OSError, AttributeError):
            pass
        return font
    except Exception as e:
        logger.warning("Failed to load variable font %s: %s", path.name, e)
        return None


def _load_static(path: Path, size: int):
    """Load a static TTF."""
    try:
        return ImageFont.truetype(str(path), size)
    except Exception as e:
        logger.warning("Failed to load font %s: %s", path.name, e)
        return None


def _build_fontset(size: int = FONT_SIZE) -> dict:
    """Return a dict of style -> ImageFont, with default-bitmap fallback."""
    noto_vf = FONT_DIR / "NotoSans-VF.ttf"
    noto_italic_vf = FONT_DIR / "NotoSans-Italic-VF.ttf"
    plex_reg = FONT_DIR / "IBMPlexMono-Regular.ttf"
    plex_bold = FONT_DIR / "IBMPlexMono-Bold.ttf"

    default = ImageFont.load_default()

    regular = _load_variation(noto_vf, size, WGHT_REGULAR)
    bold = _load_variation(noto_vf, size, WGHT_BOLD)
    italic = _load_variation(noto_italic_vf, size, WGHT_REGULAR)
    bold_italic = _load_variation(noto_italic_vf, size, WGHT_BOLD)

    # Fallback to static fonts if variable fonts fail
    if regular is None:
        regular = _load_static(FONT_DIR / "NotoSans-Regular.ttf", size) or default
    if bold is None:
        bold = _load_static(FONT_DIR / "NotoSans-Bold.ttf", size) or default
    if italic is None:
        italic = _load_static(FONT_DIR / "NotoSans-Italic.ttf", size) or default
    if bold_italic is None:
        bold_italic = _load_static(FONT_DIR / "NotoSans-BoldItalic.ttf", size) or default

    return {
        "regular": regular,
        "bold": bold,
        "italic": italic,
        "bold_italic": bold_italic,
        "code": _load_static(plex_reg, size) or default,
        "code_bold": _load_static(plex_bold, size) or default,
    }


# =============================================================================
# Inline markdown parsing
# =============================================================================


def _parse_inline(text: str) -> list[tuple[dict, str]]:
    """Split text into (style, content) segments."""
    parts = _INLINE_PATTERN.split(text)
    segments = []
    for part in parts:
        if not part:
            continue
        style = {"bold": False, "italic": False, "code": False, "underline": False}
        content = part

        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            style["code"] = True
            content = part[1:-1]
        elif part.startswith("***") and part.endswith("***") and len(part) >= 6:
            style["bold"] = True
            style["italic"] = True
            content = part[3:-3]
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            style["bold"] = True
            content = part[2:-2]
        elif part.startswith("*") and part.endswith("*") and len(part) >= 2:
            style["italic"] = True
            content = part[1:-1]
        elif part.startswith("__") and part.endswith("__") and len(part) >= 4:
            style["underline"] = True
            content = part[2:-2]

        segments.append((style, content))
    return segments


def _segment_font(fonts: dict, style: dict):
    """Pick the right font variant for a parsed segment style."""
    if style.get("code"):
        return fonts["code_bold"] if style.get("bold") else fonts["code"]
    if style.get("bold") and style.get("italic"):
        return fonts["bold_italic"]
    if style.get("bold"):
        return fonts["bold"]
    if style.get("italic"):
        return fonts["italic"]
    return fonts["regular"]


def _segment_widths(segments: list[tuple[dict, str]], fonts: dict, draw: ImageDraw.ImageDraw) -> int:
    """Sum pixel width of all segments using their per-style fonts."""
    total = 0
    for style, content in segments:
        font = _segment_font(fonts, style)
        total += int(draw.textlength(content, font=font))
        if style.get("code"):
            total += 6  # chip padding
    return total


def _draw_segment_run(
    pilmoji: "Pilmoji",
    draw: ImageDraw.ImageDraw,
    segments: list[tuple[dict, str]],
    x: int,
    y_baseline: int,
    fonts: dict,
    text_color: tuple,
    line_height: int,
):
    """Draw a list of styled segments left-to-right starting at (x, y_baseline).

    Code segments get a subtle filled background pill behind them.
    """
    cur_x = x
    for style, content in segments:
        font = _segment_font(fonts, style)
        seg_w = int(draw.textlength(content, font=font))

        if style.get("code"):
            chip_pad_x = 4
            chip_top = y_baseline - int(line_height * 0.55)
            chip_bot = y_baseline + int(line_height * 0.20)
            draw.rectangle(
                [cur_x - chip_pad_x, chip_top, cur_x + seg_w + chip_pad_x, chip_bot],
                fill=PALETTE["code_bg"],
            )
            color = PALETTE["code_text"]
        else:
            color = text_color

        pilmoji.text((cur_x, y_baseline), content, font=font, fill=color, anchor="lm")

        if style.get("underline"):
            ul_y = y_baseline + int(line_height * 0.30)
            draw.line([cur_x, ul_y, cur_x + seg_w, ul_y], fill=color, width=max(1, FONT_SIZE // 14))

        cur_x += seg_w
        if style.get("code"):
            cur_x += 6  # post-chip gap


# =============================================================================
# Column width calculation (segment-aware)
# =============================================================================


def _calc_col_widths(
    headers: list[str],
    rows: list[list[str]],
    header_fonts: dict,
    body_fonts: dict,
    padding: int,
) -> list[int]:
    """Calculate column widths using per-segment measurement."""
    img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(img)
    widths = []

    for i, header in enumerate(headers):
        header_segs = _parse_inline(str(header))
        max_w = _segment_widths(header_segs, header_fonts, draw) + padding * 2

        for row in rows:
            if i < len(row):
                cell_segs = _parse_inline(str(row[i]))
                cell_w = _segment_widths(cell_segs, body_fonts, draw) + padding * 2
                max_w = max(max_w, cell_w)

        widths.append(int(min(max_w, COLUMN_MAX_WIDTH)))

    return widths


# =============================================================================
# Text wrapping (Pilmoji-aware for emoji width)
# =============================================================================


def _wrap_segments(
    text: str,
    max_width: int,
    fonts: dict,
    pilmoji: "Pilmoji",
) -> list[str]:
    """Word-wrap text accounting for inline markdown segments and emoji width."""
    draw = pilmoji.draw
    words = text.split()
    lines = []
    current_words: list[str] = []

    for word in words:
        test_words = current_words + [word]
        test_text = " ".join(test_words)
        test_segs = _parse_inline(test_text)
        w = _segment_widths(test_segs, fonts, draw)
        if w <= max_width:
            current_words.append(word)
        else:
            if current_words:
                lines.append(" ".join(current_words))
            current_words = [word]
    if current_words:
        lines.append(" ".join(current_words))
    return lines


# =============================================================================
# Table image rendering
# =============================================================================


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

    body_fonts = _build_fontset(FONT_SIZE)
    header_fonts = _build_fontset(HEADER_FONT_SIZE)
    # Headers default-bold even without explicit **...** markup.
    header_fonts["regular"] = header_fonts["bold"]
    header_fonts["italic"] = header_fonts["bold_italic"]

    line_height = int(FONT_SIZE * LINE_HEIGHT_RATIO)
    header_line_height = int(HEADER_FONT_SIZE * LINE_HEIGHT_RATIO)

    col_widths = _calc_col_widths(sanitized_headers, sanitized_rows, header_fonts, body_fonts, PADDING)

    total_w = sum(col_widths) + len(col_widths) + 1
    total_h = HEADER_HEIGHT + len(sanitized_rows) * MIN_ROW_HEIGHT + len(sanitized_rows) + 1

    img = Image.new("RGB", (total_w, total_h), PALETTE["bg"])
    draw = ImageDraw.Draw(img)

    with Pilmoji(img) as pilmoji:
        x = 0
        for h_text, w in zip(sanitized_headers, col_widths):
            draw.rectangle(
                [x, 0, x + w, HEADER_HEIGHT],
                fill=PALETTE["header_bg"],
                outline=PALETTE["border"],
            )
            segs = _parse_inline(str(h_text))
            _draw_segment_run(
                pilmoji,
                draw,
                segs,
                x + PADDING,
                HEADER_HEIGHT // 2,
                header_fonts,
                PALETTE["header_text"],
                header_line_height,
            )
            x += w + 1

        y = HEADER_HEIGHT + 1
        for idx, row in enumerate(sanitized_rows):
            x = 0
            bg = PALETTE["row_bg_alt"] if idx % 2 else PALETTE["row_bg"]
            for cell, w in zip(row, col_widths):
                draw.rectangle([x, y, x + w, y + MIN_ROW_HEIGHT], fill=bg, outline=PALETTE["border"])
                segs = _parse_inline(str(cell))
                _draw_segment_run(
                    pilmoji,
                    draw,
                    segs,
                    x + PADDING,
                    y + MIN_ROW_HEIGHT // 2,
                    body_fonts,
                    PALETTE["text"],
                    line_height,
                )
                x += w + 1
            y += MIN_ROW_HEIGHT + 1

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf, all_links


# =============================================================================
# Table parsing
# =============================================================================


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


def _is_separator_line(line: str) -> bool:
    return bool(re.match(r"^\|[\s\-\:\|]*\|$", line.strip()))


def _parse_table_lines(lines: list[str]) -> tuple[list[str], list[list[str]], list[str]] | None:
    if not lines:
        return None
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


# =============================================================================
# Public API
# =============================================================================


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
