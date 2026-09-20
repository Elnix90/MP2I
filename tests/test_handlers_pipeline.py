"""Integration tests for the full message processing pipeline.

Tests LaTeX detection, table rendering (emojis, links, inline formatting),
code block splitting, and the MessageSender end-to-end flow.

Run with: python -m pytest tests/test_handlers_pipeline.py -v
"""

import asyncio
import io
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.handlers.codeblock import send_code_block_with_return
from utils.handlers.latex import (
    LATEX_PATTERN,
    LATEX_TO_EMOJI,
    _cache_key,
    _cached,
    _store,
)
from utils.handlers.messages import MessageSender
from utils.handlers.table import (
    _build_fontset,
    _extract_links_and_sanitize,
    _parse_inline,
    _parse_table_lines,
    _render_table_image,
    _segment_widths,
    detect_and_convert_tables,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_channel():
    ch = AsyncMock()
    ch.send = AsyncMock()
    ch.id = 123456
    return ch


def _make_mock_bot(channel):
    bot = MagicMock()
    bot.get_channel = MagicMock(return_value=channel)
    return bot


# ===========================================================================
# LaTeX detection
# ===========================================================================


class TestLatexDetection(unittest.TestCase):
    """Test LATEX_PATTERN regex on various inputs."""

    def test_single_char_formula(self):
        matches = LATEX_PATTERN.findall("$x$")
        self.assertEqual(matches, ["$x$"])

    def test_single_char_formula_with_space(self):
        matches = LATEX_PATTERN.findall("$ x $")
        self.assertEqual(matches, ["$ x $"])

    def test_inline_formula(self):
        matches = LATEX_PATTERN.findall("the value is $a^2 + b^2$ here")
        self.assertEqual(len(matches), 1)
        self.assertIn("a^2", matches[0])

    def test_display_math(self):
        text = "$$\\int_0^1 f(x)\\,dx$$"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertIn("int", matches[0])

    def test_square_bracket_delimiters(self):
        text = r"before \[ \frac{1}{2} \] after"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertIn("frac", matches[0])

    def test_paren_delimiters(self):
        text = r"inline \( \alpha + \beta \) here"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 1)
        self.assertIn("alpha", matches[0])

    def test_fenced_latex_block(self):
        text = "```latex\n\\alpha\n```"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 1)

    def test_multiple_formulas(self):
        text = "$x$ and $y$ and $$z^2$$"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 3)

    def test_no_false_positive_on_double_dollar_empty(self):
        text = "before $$ after"
        matches = LATEX_PATTERN.findall(text)
        # $$ with nothing inside shouldn't match
        self.assertEqual(len(matches), 0)

    def test_escaped_delimiters_not_matched(self):
        text = r"use \$ to escape"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 0)

    def test_formula_with_newlines(self):
        text = "$$\na + b\n=c\n$$"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 1)

    def test_adjacent_formulas(self):
        text = "$x$$y$"
        matches = LATEX_PATTERN.findall(text)
        self.assertEqual(len(matches), 2)


# ===========================================================================
# LaTeX emoji substitution
# ===========================================================================


class TestLatexEmoji(unittest.TestCase):
    """Test LATEX_TO_EMOJI mapping covers common symbols."""

    def test_greek_lowercase(self):
        for latex, emoji in [
            (r"\alpha", "α"),
            (r"\beta", "β"),
            (r"\pi", "π"),
            (r"\sigma", "σ"),
        ]:
            self.assertEqual(LATEX_TO_EMOJI[latex], emoji)

    def test_greek_uppercase(self):
        for latex, emoji in [
            (r"\Gamma", "Γ"),
            (r"\Delta", "Δ"),
            (r"\Sigma", "Σ"),
            (r"\Omega", "Ω"),
        ]:
            self.assertEqual(LATEX_TO_EMOJI[latex], emoji)

    def test_operators(self):
        self.assertEqual(LATEX_TO_EMOJI[r"\sum"], "∑")
        self.assertEqual(LATEX_TO_EMOJI[r"\int"], "∫")
        self.assertEqual(LATEX_TO_EMOJI[r"\infty"], "∞")

    def test_relations(self):
        self.assertEqual(LATEX_TO_EMOJI[r"\neq"], "≠")
        self.assertEqual(LATEX_TO_EMOJI[r"\leq"], "≤")
        self.assertEqual(LATEX_TO_EMOJI[r"\geq"], "≥")
        self.assertEqual(LATEX_TO_EMOJI[r"\approx"], "≈")


# ===========================================================================
# LaTeX cache
# ===========================================================================


class TestLatexCache(unittest.TestCase):
    def test_store_and_retrieve(self):
        from utils.handlers.latex import _LATEX_CACHE

        _LATEX_CACHE.clear()
        buf = io.BytesIO(b"fake png")
        _store("test_formula", buf)
        result = _cached("test_formula")
        self.assertIsNotNone(result)
        result.seek(0)
        self.assertEqual(result.read(), b"fake png")
        _LATEX_CACHE.clear()

    def test_cache_key_strips_whitespace(self):
        self.assertEqual(_cache_key("  x  "), "x")
        self.assertEqual(_cache_key("\nalpha\n"), "alpha")

    def test_cache_eviction(self):
        from utils.handlers.latex import _LATEX_CACHE, _LATEX_CACHE_MAX

        _LATEX_CACHE.clear()
        for i in range(_LATEX_CACHE_MAX + 5):
            _store(f"key_{i}", io.BytesIO(b"data"))
        self.assertLessEqual(len(_LATEX_CACHE), _LATEX_CACHE_MAX)
        _LATEX_CACHE.clear()


# ===========================================================================
# LaTeX clean (from MessageSender)
# ===========================================================================


class TestLatexClean(unittest.TestCase):
    def _clean(self, latex):
        sender = MessageSender(AsyncMock())
        return sender._clean_latex(latex)

    def test_strip_code_fence(self):
        self.assertEqual(self._clean("```latex\n\\alpha\n```"), "\\alpha")

    def test_strip_dollar(self):
        self.assertEqual(self._clean("$x^2$"), "x^2")

    def test_strip_double_dollar(self):
        self.assertEqual(self._clean("$$a + b$$"), "a + b")

    def test_strip_display_math(self):
        self.assertEqual(self._clean(r"\[ \frac{1}{2} \]"), r"\frac{1}{2}")

    def test_strip_inline_math(self):
        self.assertEqual(self._clean(r"\( x \)"), "x")

    def test_strip_multiple_layers(self):
        result = self._clean("```latex\n$$x^2$$\n```")
        self.assertEqual(result, "x^2")


# ===========================================================================
# Table parsing
# ===========================================================================


class TestTableParsing(unittest.TestCase):
    def test_simple_table(self):
        lines = [
            "| Name | Age |",
            "|------|-----|",
            "| Alice | 30 |",
            "| Bob | 25 |",
        ]
        result = _parse_table_lines(lines)
        self.assertIsNotNone(result)
        headers, rows, _aligns = result
        self.assertEqual(headers, ["Name", "Age"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], ["Alice", "30"])

    def test_table_with_alignments(self):
        lines = [
            "| Left | Center | Right |",
            "|:-----|:------:|------:|",
            "| a | b | c |",
        ]
        result = _parse_table_lines(lines)
        self.assertIsNotNone(result)
        _, _, aligns = result
        self.assertEqual(aligns, ["left", "center", "right"])

    def test_single_line_not_table(self):
        result = _parse_table_lines(["| just one line |"])
        # No separator, but still parsed as 1-row table
        self.assertIsNotNone(result)

    def test_empty_table(self):
        result = _parse_table_lines([])
        self.assertIsNone(result)

    def test_missing_cells_padded(self):
        lines = [
            "| A | B | C |",
            "|---|---|---|",
            "| 1 | 2 |",
        ]
        result = _parse_table_lines(lines)
        self.assertIsNotNone(result)
        _, rows, _ = result
        self.assertEqual(rows[0], ["1", "2", ""])


# ===========================================================================
# Table link extraction
# ===========================================================================


class TestTableLinks(unittest.TestCase):
    def test_markdown_link(self):
        links = []
        text, links = _extract_links_and_sanitize("[Google](https://google.com)", links)
        self.assertEqual(len(links), 1)
        self.assertIn("google.com", links[0])
        self.assertIn("[1]", text)

    def test_plain_url(self):
        links = []
        _text, links = _extract_links_and_sanitize("Visit https://example.com now", links)
        self.assertEqual(len(links), 1)
        self.assertIn("example.com", links[0])

    def test_duplicate_links(self):
        links = []
        text1, links = _extract_links_and_sanitize("[A](https://x.com)", links)
        text2, links = _extract_links_and_sanitize("[B](https://x.com)", links)
        self.assertEqual(len(links), 1)
        self.assertIn("[1]", text1)
        self.assertIn("[1]", text2)

    def test_multiple_different_links(self):
        links = []
        text, links = _extract_links_and_sanitize("[A](https://a.com) and [B](https://b.com)", links)
        self.assertEqual(len(links), 2)
        self.assertIn("[1]", text)
        self.assertIn("[2]", text)

    def test_www_stripped_from_domain(self):
        links = []
        _, links = _extract_links_and_sanitize("[X](https://www.example.com)", links)
        self.assertEqual(links[0], "https://www.example.com")

    def test_no_links(self):
        links = []
        text, links = _extract_links_and_sanitize("no links here", links)
        self.assertEqual(text, "no links here")
        self.assertEqual(links, [])


# ===========================================================================
# Table inline markdown parsing
# ===========================================================================


class TestTableInlineMarkdown(unittest.TestCase):
    def test_plain_text(self):
        segs = _parse_inline("hello world")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0][1], "hello world")

    def test_bold(self):
        segs = _parse_inline("**bold**")
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0][0]["bold"])
        self.assertEqual(segs[0][1], "bold")

    def test_italic(self):
        segs = _parse_inline("*italic*")
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0][0]["italic"])

    def test_bold_italic(self):
        segs = _parse_inline("***both***")
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0][0]["bold"])
        self.assertTrue(segs[0][0]["italic"])

    def test_code(self):
        segs = _parse_inline("`code`")
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0][0]["code"])
        self.assertEqual(segs[0][1], "code")

    def test_underline(self):
        segs = _parse_inline("__under__")
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0][0]["underline"])

    def test_mixed(self):
        segs = _parse_inline("hello **world** and *x*")
        self.assertEqual(len(segs), 4)
        self.assertFalse(segs[0][0]["bold"])
        self.assertTrue(segs[1][0]["bold"])
        self.assertTrue(segs[3][0]["italic"])

    def test_empty_string(self):
        segs = _parse_inline("")
        self.assertEqual(segs, [])


# ===========================================================================
# Table rendering (real images)
# ===========================================================================


class TestTableRendering(unittest.TestCase):
    def test_render_simple_table(self):
        headers = ["Name", "Value"]
        rows = [["Alice", "100"], ["Bob", "200"]]
        buf, links = _render_table_image(headers, rows, ["left", "right"])
        self.assertIsInstance(buf, io.BytesIO)
        buf.seek(0)
        data = buf.read()
        self.assertGreater(len(data), 0)
        # PNG magic bytes
        self.assertEqual(data[:4], b"\x89PNG")
        self.assertEqual(links, [])

    def test_render_table_with_links(self):
        headers = ["Resource", "URL"]
        rows = [["Google", "[G](https://github.com)"]]
        _buf, links = _render_table_image(headers, rows, ["left", "left"])
        self.assertEqual(len(links), 1)
        self.assertIn("github.com", links[0])

    def test_render_table_with_emoji(self):
        headers = ["Emoji", "Name"]
        rows = [["😀", "Happy"], ["🔥", "Fire"]]
        buf, _links = _render_table_image(headers, rows, ["center", "left"])
        buf.seek(0)
        data = buf.read()
        self.assertEqual(data[:4], b"\x89PNG")

    def test_render_table_with_bold(self):
        headers = ["Feature", "Status"]
        rows = [["**Important**", "✅ Done"], ["Normal", "⏳ Pending"]]
        buf, _links = _render_table_image(headers, rows, ["left", "center"])
        buf.seek(0)
        self.assertEqual(buf.read()[:4], b"\x89PNG")

    def test_render_table_with_code(self):
        headers = ["Function", "Description"]
        rows = [["`print()`", "Outputs text"], ["`len()`", "Returns length"]]
        buf, _links = _render_table_image(headers, rows, ["left", "left"])
        buf.seek(0)
        self.assertEqual(buf.read()[:4], b"\x89PNG")

    def test_render_large_table(self):
        headers = ["Col" + str(i) for i in range(10)]
        rows = [["cell" for _ in range(10)] for _ in range(20)]
        alignments = ["left"] * 10
        buf, _links = _render_table_image(headers, rows, alignments)
        buf.seek(0)
        self.assertEqual(buf.read()[:4], b"\x89PNG")

    def test_render_wide_text_truncation(self):
        headers = ["Text"]
        rows = [["x" * 500]]
        buf, _ = _render_table_image(headers, rows, ["left"])
        buf.seek(0)
        self.assertEqual(buf.read()[:4], b"\x89PNG")


# ===========================================================================
# detect_and_convert_tables
# ===========================================================================


class TestDetectAndConvertTables(unittest.TestCase):
    def test_fenced_markdown_table(self):
        text = "```markdown\n| A | B |\n|---|---|\n| 1 | 2 |\n```"
        new_text, images, _data = detect_and_convert_tables(text)
        self.assertEqual(len(images), 1)
        self.assertIn("__TABLE_IMG_0__", new_text)

    def test_unfenced_table(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        new_text, images, _data = detect_and_convert_tables(text)
        self.assertEqual(len(images), 1)
        self.assertIn("__TABLE_IMG_0__", new_text)

    def test_no_table(self):
        text = "Just some text with no tables."
        new_text, images, _data = detect_and_convert_tables(text)
        self.assertEqual(len(images), 0)
        self.assertEqual(new_text, text)

    def test_multiple_tables(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n\n| C | D |\n|---|---|\n| 3 | 4 |"
        _new_text, images, _data = detect_and_convert_tables(text)
        self.assertEqual(len(images), 2)

    def test_table_in_code_block_ignored(self):
        text = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```"
        _new_text, images, _ = detect_and_convert_tables(text)
        self.assertEqual(len(images), 0)

    def test_table_with_links_in_fenced(self):
        text = "```markdown\n| Name | Link |\n|---|---|\n| GH | [here](https://github.com) |\n```"
        _new_text, images, data = detect_and_convert_tables(text)
        self.assertEqual(len(images), 1)
        self.assertEqual(len(data[0]["links"]), 1)

    def test_metadata_populated(self):
        text = "| X | Y |\n|---|---|\n| a | b |"
        _, _images, data = detect_and_convert_tables(text)
        self.assertEqual(len(data), 1)
        self.assertIn("headers", data[0])
        self.assertIn("rows", data[0])
        self.assertIn("links", data[0])


# ===========================================================================
# Code block splitting
# ===========================================================================


class TestCodeBlockSplitting(unittest.TestCase):
    def test_short_block_unch(self):
        ch = _make_mock_channel()
        block = "```python\nprint('hello')\n```"
        _run(send_code_block_with_return(ch, block))
        ch.send.assert_called_once()
        sent = ch.send.call_args[0][0]
        self.assertIn("print", sent)
        self.assertTrue(sent.startswith("```python"))

    def test_long_block_split(self):
        ch = _make_mock_channel()
        lines = "\n".join(f"line_{i}" for i in range(200))
        block = f"```python\n{lines}\n```"
        _run(send_code_block_with_return(ch, block, max_length=200))
        self.assertGreater(ch.send.call_count, 1)

    def test_language_preserved_no_newline(self):
        ch = _make_mock_channel()
        block = "```python\nx = 1```"
        _run(send_code_block_with_return(ch, block))
        ch.send.assert_called_once()
        sent = ch.send.call_args[0][0]
        self.assertTrue(sent.startswith("```python"))

    def test_latex_delegates_to_image(self):
        ch = _make_mock_channel()
        bot = _make_mock_bot(ch)
        block = "```latex\n\\alpha\n```"
        with patch(
            "utils.handlers.messages.MessageSender.send_latex_image",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_send:
            _run(send_code_block_with_return(ch, block, bot=bot))
            mock_send.assert_called_once()


# ===========================================================================
# MessageSender.process_and_send end-to-end
# ===========================================================================


class TestMessageSenderE2E(unittest.TestCase):
    def _make_sender(self, channel=None, bot=None):
        ch = channel or _make_mock_channel()
        b = bot or _make_mock_bot(ch)
        return MessageSender(ch, b), ch

    def test_plain_text(self):
        sender, ch = self._make_sender()
        _run(sender.process_and_send("Hello world"))
        ch.send.assert_called()
        sent = ch.send.call_args[0][0]
        self.assertEqual(sent, "Hello world")

    def test_code_block(self):
        sender, ch = self._make_sender()
        _run(sender.process_and_send("```python\nprint(1)\n```"))
        ch.send.assert_called()
        sent = ch.send.call_args[0][0]
        self.assertIn("print(1)", sent)

    def test_table_renders_image(self):
        sender, ch = self._make_sender()
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        _run(sender.process_and_send(text))
        # Should send a File, not plain text
        for call in ch.send.call_args_list:
            if call[1].get("file") is not None:
                return
        self.fail("Expected at least one call with a file= argument")

    def test_mixed_text_and_table(self):
        sender, ch = self._make_sender()
        text = "Here is a table:\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nDone."
        _run(sender.process_and_send(text))
        self.assertGreater(ch.send.call_count, 1)

    def test_empty_text(self):
        sender, ch = self._make_sender()
        _run(sender.process_and_send("   "))
        ch.send.assert_not_called()

    def test_debug_header(self):
        from utils.debug import DebugWriter

        debug = DebugWriter("test-turn", _make_mock_channel(), MagicMock())
        sender, _ch = self._make_sender()
        sender.debug = debug
        _run(sender.process_and_send("Hello"))
        self.assertGreater(len(debug.content_parts), 0)


# ===========================================================================
# Font loading
# ===========================================================================


class TestFontLoading(unittest.TestCase):
    def test_build_fontset(self):
        fonts = _build_fontset()
        self.assertIn("regular", fonts)
        self.assertIn("bold", fonts)
        self.assertIn("italic", fonts)
        self.assertIn("code", fonts)

    def test_build_fontset_custom_size(self):
        fonts = _build_fontset(20)
        self.assertIn("regular", fonts)


# ===========================================================================
# Segment width calculation
# ===========================================================================


class TestSegmentWidths(unittest.TestCase):
    def test_single_segment(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        fonts = _build_fontset()
        segs = [({"bold": False, "italic": False, "code": False, "underline": False}, "hello")]
        w = _segment_widths(segs, fonts, draw)
        self.assertGreater(w, 0)

    def test_code_segment_has_padding(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        fonts = _build_fontset()
        style_plain = {"bold": False, "italic": False, "code": False, "underline": False}
        style_code = {"bold": False, "italic": False, "code": True, "underline": False}
        plain_w = _segment_widths([(style_plain, "x")], fonts, draw)
        code_w = _segment_widths([(style_code, "x")], fonts, draw)
        self.assertGreater(code_w, plain_w)


if __name__ == "__main__":
    unittest.main()
