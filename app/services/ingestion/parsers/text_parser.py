from __future__ import annotations

from app.services.ingestion.models import NormalizedDocument, NormalizedSection, SourceFile
from app.services.ingestion.parsers.base import DocumentParser


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except Exception:
            continue
    return content.decode("utf-8", errors="replace")


class TextParser(DocumentParser):
    def supports(self, source: SourceFile) -> bool:
        return source.extension in {".txt", ".md", ".markdown"}

    def parse(self, content: bytes, source: SourceFile) -> NormalizedDocument:
        text = _decode_text(content).strip()
        heading = "Markdown" if source.extension in {".md", ".markdown"} else "Text"
        parse_warnings: list[str] = []
        if source.extension in {".md", ".markdown"}:
            try:
                from markdown_it import MarkdownIt

                tokens = MarkdownIt().parse(text)
                heading_count = sum(1 for token in tokens if token.type == "heading_open")
                heading = f"Markdown ({heading_count} headings)"
            except Exception:
                parse_warnings.append("markdown-it-py unavailable or failed; used plain text parsing.")

        section = NormalizedSection(section_id="body", order=0, heading=heading, text=text)
        return NormalizedDocument(
            source=source,
            sections=[section],
            raw_text=text,
            metadata={"characters": len(text)},
            parse_warnings=parse_warnings,
        )
