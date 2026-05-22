from __future__ import annotations

from app.services.ingestion.models import NormalizedDocument, NormalizedSection, SourceFile
from app.services.ingestion.parsers.base import DocumentParser


class PdfParser(DocumentParser):
    def supports(self, source: SourceFile) -> bool:
        return source.extension == ".pdf"

    def parse(self, content: bytes, source: SourceFile) -> NormalizedDocument:
        from io import BytesIO

        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF parser dependency missing. Install pypdf.") from exc

        reader = PdfReader(BytesIO(content))
        sections: list[NormalizedSection] = []
        for idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            sections.append(
                NormalizedSection(
                    section_id=f"page-{idx + 1}",
                    order=idx,
                    heading=f"Page {idx + 1}",
                    page=idx + 1,
                    text=text,
                )
            )

        raw_text = "\n\n".join(section.text for section in sections)
        return NormalizedDocument(
            source=source,
            sections=sections,
            raw_text=raw_text,
            metadata={"pages": len(reader.pages)},
            parse_warnings=[] if sections else ["No extractable text found in PDF."],
        )
