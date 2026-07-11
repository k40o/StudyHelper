"""Core document domain model.

This module is intentionally dependency-free (pure Python). Every parser in
``infrastructure/parsing`` converts a raw file into these structures, so the
rest of the application never needs to know whether a fact originally came from
a Word doc, a slide, or a PDF page.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    """The kind of file a document was parsed from."""

    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    TXT = "txt"


class BlockType(str, Enum):
    """The semantic role of a piece of content within a document."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"


@dataclass
class SourceLocation:
    """Where a block physically lives in the source file.

    Used later to cite the exact page/slide in generated questions and tutor
    answers. ``None`` means the format has no such concept (Word/TXT flow
    continuously and have no intrinsic page numbers until rendered).
    """

    page: Optional[int] = None   # 1-based, for PDFs
    slide: Optional[int] = None  # 1-based, for PowerPoint

    def describe(self) -> str:
        if self.slide is not None:
            return f"slide {self.slide}"
        if self.page is not None:
            return f"page {self.page}"
        return ""


@dataclass
class ContentBlock:
    """A single, atomic unit of extracted content."""

    text: str
    block_type: BlockType = BlockType.PARAGRAPH
    level: int = 0  # heading depth (1 = top level); 0 for non-headings
    location: SourceLocation = field(default_factory=SourceLocation)

    @property
    def is_heading(self) -> bool:
        return self.block_type == BlockType.HEADING


@dataclass
class ParsedDocument:
    """A fully parsed document: an ordered list of content blocks plus metadata."""

    file_path: str
    source_type: SourceType
    title: str
    blocks: list[ContentBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """All block text joined with newlines (for embedding / full-text search)."""
        return "\n".join(b.text for b in self.blocks if b.text.strip())

    @property
    def headings(self) -> list[ContentBlock]:
        return [b for b in self.blocks if b.is_heading]

    @property
    def word_count(self) -> int:
        return sum(len(b.text.split()) for b in self.blocks)

    def blocks_on(self, *, page: int | None = None, slide: int | None = None) -> list[ContentBlock]:
        """Return blocks located on a specific page or slide."""
        return [
            b
            for b in self.blocks
            if (page is not None and b.location.page == page)
            or (slide is not None and b.location.slide == slide)
        ]
