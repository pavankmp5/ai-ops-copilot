from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SourceFile:
    filename: str
    mime_type: str
    extension: str
    checksum: str | None = None


@dataclass(slots=True)
class NormalizedSection:
    section_id: str
    text: str
    order: int
    heading: str | None = None
    page: int | None = None
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedDocument:
    source: SourceFile
    sections: list[NormalizedSection]
    raw_text: str
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    chunk_index: int
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)
