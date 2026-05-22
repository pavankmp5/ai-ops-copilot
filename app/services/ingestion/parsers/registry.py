from __future__ import annotations

from fastapi import HTTPException, status

from app.services.ingestion.models import SourceFile
from app.services.ingestion.parsers.base import DocumentParser
from app.services.ingestion.parsers.csv_parser import CsvParser
from app.services.ingestion.parsers.docx_parser import DocxParser
from app.services.ingestion.parsers.pdf_parser import PdfParser
from app.services.ingestion.parsers.text_parser import TextParser

_PARSERS: list[DocumentParser] = [
    CsvParser(),
    TextParser(),
    PdfParser(),
    DocxParser(),
]


def resolve_parser(source: SourceFile) -> DocumentParser:
    for parser in _PARSERS:
        if parser.supports(source):
            return parser

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No parser available for extension '{source.extension}'.",
    )
