"""Document parsing service — the single entry point for turning a file on disk
into a :class:`ParsedDocument`.

It owns a list of parser strategies and dispatches to the first one that can
handle a given file. Callers depend only on this service, never on individual
parsers (Dependency Inversion).
"""
from __future__ import annotations

from pathlib import Path

from ...domain.document import ParsedDocument
from .base import DocumentParser, UnsupportedFormatError
from .docx_parser import DocxParser
from .pdf_parser import PdfParser
from .pptx_parser import PptxParser
from .txt_parser import TxtParser


def default_parsers() -> list[DocumentParser]:
    """The parsers shipped by default, one per supported format."""
    return [TxtParser(), DocxParser(), PptxParser(), PdfParser()]


class DocumentParsingService:
    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        self._parsers = parsers if parsers is not None else default_parsers()

    @property
    def supported_extensions(self) -> set[str]:
        return {ext for parser in self._parsers for ext in parser.extensions}

    def can_parse(self, path: str | Path) -> bool:
        path = Path(path)
        return any(parser.can_parse(path) for parser in self._parsers)

    def parse(self, path: str | Path) -> ParsedDocument:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser.parse(path)
        raise UnsupportedFormatError(
            f"No parser for '{path.suffix}'. Supported: {sorted(self.supported_extensions)}"
        )
