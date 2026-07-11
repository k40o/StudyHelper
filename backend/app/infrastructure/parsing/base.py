"""Parser strategy interface.

Each concrete parser handles exactly one family of file formats. Adding support
for a new format means adding a new class here — no existing code changes
(Open/Closed Principle).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ...domain.document import ParsedDocument


class ParserError(Exception):
    """Raised when a file exists and matches a parser but cannot be read."""


class UnsupportedFormatError(Exception):
    """Raised when no registered parser can handle a file."""


class DocumentParser(ABC):
    """Strategy interface implemented by one parser per format family."""

    #: File extensions this parser handles, lowercase, including the dot.
    extensions: tuple[str, ...] = ()

    def can_parse(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Read ``path`` and return a normalized :class:`ParsedDocument`."""
        raise NotImplementedError


def derive_title(path: Path, blocks_first_heading: str | None = None) -> str:
    """Best-effort human title: first heading, else the file name."""
    if blocks_first_heading:
        return blocks_first_heading.strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()
