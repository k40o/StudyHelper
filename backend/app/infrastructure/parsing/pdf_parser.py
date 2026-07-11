"""PDF parser, built on PyMuPDF (fitz).

PDFs have no style metadata, so we infer structure from font sizes: we measure
the document's dominant ("body") font size, then flag lines that are noticeably
larger as headings. Every block is tagged with its 1-based page number for
citations.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from ...domain.document import (
    BlockType,
    ContentBlock,
    ParsedDocument,
    SourceLocation,
    SourceType,
)
from .base import DocumentParser, ParserError, derive_title
from .heuristics import heading_level_from_font


class PdfParser(DocumentParser):
    extensions = (".pdf",)

    def parse(self, path: Path) -> ParsedDocument:
        try:
            import fitz  # PyMuPDF, lazy import
        except ImportError as exc:  # pragma: no cover
            raise ParserError("PyMuPDF (fitz) is not installed") from exc

        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            raise ParserError(f"Could not open PDF {path}: {exc}") from exc

        try:
            lines = self._collect_lines(doc)
            body_size = self._dominant_font_size(lines)
            blocks = self._to_blocks(lines, body_size)
            page_count = doc.page_count
            pdf_title = (doc.metadata or {}).get("title", "").strip() or None
        finally:
            doc.close()

        first_heading = next((b.text for b in blocks if b.is_heading), None)
        total_chars = sum(len(b.text) for b in blocks)
        # A normal text-based PDF has hundreds of characters per page; a
        # scanned/image-only PDF (no OCR here) yields almost nothing — just
        # stray header/footer/page-number text PyMuPDF happens to find.
        low_text = page_count > 0 and (total_chars / page_count) < 30
        return ParsedDocument(
            file_path=str(path),
            source_type=SourceType.PDF,
            title=pdf_title or derive_title(path, first_heading),
            blocks=blocks,
            metadata={"page_count": page_count, "low_text_warning": low_text},
        )

    @staticmethod
    def _collect_lines(doc) -> list[tuple[str, float, int]]:
        """Return ``(text, max_font_size, page_number)`` for every non-empty line."""
        lines: list[tuple[str, float, int]] = []
        for page_index in range(doc.page_count):
            page = doc[page_index]
            page_no = page_index + 1
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    max_size = max((s.get("size", 0.0) for s in spans), default=0.0)
                    lines.append((text, max_size, page_no))
        return lines

    @staticmethod
    def _dominant_font_size(lines) -> float:
        """Body font size = the size covering the most *characters*.

        Weighting by character count (not line count) is robust: body text
        always has far more characters than the handful of larger heading lines,
        so headings can't win even when they occupy a similar number of lines.
        """
        if not lines:
            return 0.0
        weight: Counter[float] = Counter()
        for text, size, _ in lines:
            if size > 0:
                weight[round(size, 1)] += len(text)
        if not weight:
            return 0.0
        return weight.most_common(1)[0][0]

    @staticmethod
    def _to_blocks(lines, body_size: float) -> list[ContentBlock]:
        blocks: list[ContentBlock] = []
        for text, size, page_no in lines:
            location = SourceLocation(page=page_no)
            level = heading_level_from_font(size, body_size)
            if level is not None and len(text) <= 120:
                blocks.append(
                    ContentBlock(text=text, block_type=BlockType.HEADING, level=level, location=location)
                )
            else:
                blocks.append(
                    ContentBlock(text=text, block_type=BlockType.PARAGRAPH, location=location)
                )
        return blocks
