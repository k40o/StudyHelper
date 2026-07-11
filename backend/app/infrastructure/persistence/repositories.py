"""Repositories: the only place that translates between domain objects
(:class:`ParsedDocument`) and ORM rows. Services depend on these, not on the
ORM directly (Dependency Inversion + Repository pattern).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.document import ContentBlock, ParsedDocument, SourceLocation, SourceType
from .models import BlockRecord, DocumentRecord, UserRecord


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_email(self, email: str) -> UserRecord | None:
        stmt = select(UserRecord).where(UserRecord.email == email.lower().strip())
        return self.session.scalar(stmt)

    def get_by_id(self, user_id: int) -> UserRecord | None:
        return self.session.get(UserRecord, user_id)

    def create(self, email: str, password_hash: str) -> UserRecord:
        record = UserRecord(email=email.lower().strip(), password_hash=password_hash)
        self.session.add(record)
        self.session.flush()
        return record


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- reads ------------------------------------------------------------- #
    def get_by_path(self, file_path: str) -> DocumentRecord | None:
        stmt = select(DocumentRecord).where(DocumentRecord.file_path == file_path)
        return self.session.scalar(stmt)

    def get_by_id(self, document_id: int, user_id: int | None = None) -> DocumentRecord | None:
        record = self.session.get(DocumentRecord, document_id)
        if record is None:
            return None
        if user_id is not None and record.user_id != user_id:
            return None
        return record

    def hash_for_path(self, file_path: str) -> str | None:
        record = self.get_by_path(file_path)
        return record.content_hash if record else None

    def list_all(self, user_id: int) -> list[DocumentRecord]:
        stmt = (
            select(DocumentRecord)
            .where(DocumentRecord.user_id == user_id)
            .order_by(DocumentRecord.title)
        )
        return list(self.session.scalars(stmt))

    def count(self, user_id: int) -> int:
        return (
            self.session.query(DocumentRecord)
            .filter(DocumentRecord.user_id == user_id)
            .count()
        )

    # --- writes ------------------------------------------------------------ #
    def upsert(self, parsed: ParsedDocument, content_hash: str, user_id: int) -> DocumentRecord:
        """Insert a new document or replace an existing one at the same path.

        Blocks are always fully rebuilt (cascade-delete then re-add) so a
        re-imported, edited file never leaves stale content behind.
        """
        record = self.get_by_path(parsed.file_path)
        if record is None:
            record = DocumentRecord(file_path=parsed.file_path, user_id=user_id)
            self.session.add(record)

        record.source_type = parsed.source_type.value
        record.title = parsed.title
        record.content_hash = content_hash
        record.word_count = parsed.word_count
        record.doc_metadata = parsed.metadata or {}

        record.blocks = [
            BlockRecord(
                position=i,
                text=block.text,
                block_type=block.block_type.value,
                level=block.level,
                page=block.location.page,
                slide=block.location.slide,
            )
            for i, block in enumerate(parsed.blocks)
        ]
        return record

    def delete_by_path(self, file_path: str) -> bool:
        record = self.get_by_path(file_path)
        if record is None:
            return False
        self.session.delete(record)
        return True

    def delete_by_id(self, document_id: int) -> bool:
        record = self.get_by_id(document_id)
        if record is None:
            return False
        self.session.delete(record)
        return True


def record_to_domain(record: DocumentRecord) -> ParsedDocument:
    """Reconstruct a domain :class:`ParsedDocument` from a stored row."""
    from ...domain.document import BlockType  # local import avoids cycle at module load

    return ParsedDocument(
        file_path=record.file_path,
        source_type=SourceType(record.source_type),
        title=record.title,
        blocks=[
            ContentBlock(
                text=b.text,
                block_type=BlockType(b.block_type),
                level=b.level,
                location=SourceLocation(page=b.page, slide=b.slide),
            )
            for b in record.blocks
        ],
        metadata=record.doc_metadata or {},
    )
