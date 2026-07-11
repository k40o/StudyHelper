"""Heading/structure detection heuristics for formats that don't carry explicit
style information (plain text, and PDF where we only have font sizes).

Word and PowerPoint tell us directly what a heading is (paragraph styles, slide
title placeholders), so they don't need these guesses.
"""
from __future__ import annotations

import re

from ...domain.document import BlockType

# "Chapter 3", "Section 2.1", "Unit IV", "Part 1" -> strong heading signal
_CHAPTER_RE = re.compile(
    r"^(chapter|section|unit|part|lesson|module|topic)\b[\s:.\-]*\w+",
    re.IGNORECASE,
)
# Markdown-style heading: leading #'s
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# Bullet list markers
_BULLET_RE = re.compile(r"^\s*([-*•·▪◦]|\d+[.)])\s+")


def classify_line(line: str) -> tuple[BlockType, int, str]:
    """Classify a single line of plain text.

    Returns ``(block_type, heading_level, cleaned_text)``. ``cleaned_text``
    strips markdown/bullet markers so the stored text is clean.
    """
    stripped = line.strip()

    # Markdown heading: "## Title" -> level 2
    md = _MD_HEADING_RE.match(stripped)
    if md:
        level = len(md.group(1))
        return BlockType.HEADING, level, md.group(2).strip()

    # Chapter/Section style heading
    if _CHAPTER_RE.match(stripped):
        return BlockType.HEADING, 1, stripped

    # Bullet / numbered list item
    bullet = _BULLET_RE.match(stripped)
    if bullet:
        return BlockType.LIST_ITEM, 0, _BULLET_RE.sub("", stripped).strip()

    # Short, ALL-CAPS, no trailing sentence punctuation -> likely a heading
    if _looks_like_caps_heading(stripped):
        return BlockType.HEADING, 2, stripped

    return BlockType.PARAGRAPH, 0, stripped


def _looks_like_caps_heading(text: str) -> bool:
    if not (3 <= len(text) <= 70):
        return False
    if text.endswith((".", "!", "?", ",", ";", ":")):
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    # Must have at least a couple of words worth of letters, mostly uppercase.
    upper_ratio = sum(c.isupper() for c in letters) / len(letters)
    return upper_ratio >= 0.85


def heading_level_from_font(size: float, body_size: float) -> int | None:
    """Infer a heading level from a PDF line's font size relative to body text.

    Returns ``None`` if the line is body text, else a heading level 1-3
    (bigger relative size -> smaller/more important level number).
    """
    if body_size <= 0:
        return None
    ratio = size / body_size
    if ratio >= 1.5:
        return 1
    if ratio >= 1.25:
        return 2
    if ratio >= 1.12:
        return 3
    return None
