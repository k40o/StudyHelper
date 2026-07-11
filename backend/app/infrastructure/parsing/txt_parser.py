"""Plain-text (.txt / .md) parser."""
from __future__ import annotations

from pathlib import Path

from ...domain.document import BlockType, ContentBlock, ParsedDocument, SourceType
from .base import DocumentParser, ParserError, derive_title
from .heuristics import classify_line


class TxtParser(DocumentParser):
    extensions = (".txt", ".md", ".markdown")

    def parse(self, path: Path) -> ParsedDocument:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - filesystem error
            raise ParserError(f"Could not read {path}: {exc}") from exc

        blocks: list[ContentBlock] = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            block_type, level, text = classify_line(line)
            if text:
                blocks.append(ContentBlock(text=text, block_type=block_type, level=level))

        first_heading = next((b.text for b in blocks if b.is_heading), None)
        return ParsedDocument(
            file_path=str(path),
            source_type=SourceType.TXT,
            title=derive_title(path, first_heading),
            blocks=blocks,
            metadata={"line_count": len(blocks)},
        )
