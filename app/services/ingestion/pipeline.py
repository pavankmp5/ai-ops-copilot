from __future__ import annotations

import hashlib

from app.services.ingestion.detector import detect_file_type
from app.services.ingestion.models import NormalizedDocument, SourceFile
from app.services.ingestion.parsers.registry import resolve_parser


def _build_source(filename: str, content_type: str | None, content: bytes) -> SourceFile:
    extension, mime_type = detect_file_type(filename, content_type)
    checksum = hashlib.sha256(content).hexdigest()
    return SourceFile(
        filename=filename,
        mime_type=mime_type,
        extension=extension,
        checksum=checksum,
    )


def parse_uploaded_document(*, filename: str, content_type: str | None, content: bytes) -> NormalizedDocument:
    source = _build_source(filename, content_type, content)
    parser = resolve_parser(source)
    return parser.parse(content, source)


def parse_stored_document(*, filename: str, content: bytes) -> NormalizedDocument:
    source = _build_source(filename, None, content)
    parser = resolve_parser(source)
    return parser.parse(content, source)
