from __future__ import annotations

from app.services.ingestion.models import DocumentChunk, NormalizedDocument


def _chunk_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks


def build_chunks(document: NormalizedDocument, *, max_chars: int = 1200, overlap_chars: int = 200) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    chunk_index = 0
    for section in document.sections:
        for text_chunk in _chunk_text(section.text, max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{section.section_id}:chunk:{chunk_index}",
                    text=text_chunk,
                    chunk_index=chunk_index,
                    metadata={
                        "section_id": section.section_id,
                        "section_order": section.order,
                        "heading": section.heading,
                        "page": section.page,
                    },
                )
            )
            chunk_index += 1
    return chunks
