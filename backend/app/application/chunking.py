"""Turn a parsed document into retrieval chunks.

Chunks are the unit of RAG retrieval. We group consecutive blocks under their
most recent heading, capping each chunk at a target size so embeddings stay
focused, and we remember the heading + page/slide of each chunk for citations.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain.document import ParsedDocument

DEFAULT_MAX_CHARS = 900
DEFAULT_MIN_CHARS = 150


@dataclass
class Chunk:
    text: str
    index: int
    heading: str | None = None
    page: int | None = None
    slide: int | None = None


def chunk_document(
    doc: ParsedDocument,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buf_len = 0
    has_body = False  # buffer holds at least one non-heading block
    current_heading: str | None = None
    start_page: int | None = None
    start_slide: int | None = None
    index = 0

    def flush() -> None:
        nonlocal buffer, buf_len, index, start_page, start_slide, has_body
        text = "\n".join(buffer).strip()
        if text:
            chunks.append(
                Chunk(
                    text=text,
                    index=index,
                    heading=current_heading,
                    page=start_page,
                    slide=start_slide,
                )
            )
            index += 1
        buffer = []
        buf_len = 0
        has_body = False
        start_page = start_slide = None

    for block in doc.blocks:
        if not block.text.strip():
            continue

        if block.is_heading:
            # A new heading starts a new section — but only break if the current
            # buffer already has real content (avoids lone heading-only chunks
            # when headings stack, e.g. a title immediately followed by a subtitle).
            if has_body:
                flush()
            current_heading = block.text

        if not buffer:
            start_page = block.location.page
            start_slide = block.location.slide

        buffer.append(block.text)
        buf_len += len(block.text) + 1
        if not block.is_heading:
            has_body = True

        # Size cap: split very long sections so embeddings stay focused.
        if buf_len >= max_chars and has_body:
            flush()

    flush()
    _ = min_chars  # reserved for future tuning; retained for API stability
    return chunks
