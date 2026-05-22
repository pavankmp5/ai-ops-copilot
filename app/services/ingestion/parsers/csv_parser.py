from __future__ import annotations

from io import BytesIO

import pandas as pd

from app.services.ingestion.models import NormalizedDocument, NormalizedSection, SourceFile
from app.services.ingestion.parsers.base import DocumentParser


class CsvParser(DocumentParser):
    def supports(self, source: SourceFile) -> bool:
        return source.extension == ".csv"

    def parse(self, content: bytes, source: SourceFile) -> NormalizedDocument:
        dataframe = pd.read_csv(BytesIO(content))
        preview_rows = dataframe.head(10).to_csv(index=False)
        columns = ", ".join(str(column) for column in dataframe.columns)
        numeric_columns = list(dataframe.select_dtypes(include="number").columns)
        numeric_summary = "No numeric summary available."
        if numeric_columns:
            numeric_summary = dataframe[numeric_columns[:8]].describe().round(2).to_string()

        sections = [
            NormalizedSection(
                section_id="overview",
                order=0,
                heading="Overview",
                text="\n".join(
                    [
                        f"Filename: {source.filename}",
                        f"Rows: {len(dataframe)}",
                        f"Columns: {columns or 'No columns'}",
                    ]
                ),
            ),
            NormalizedSection(
                section_id="summary",
                order=1,
                heading="Numeric Summary",
                text=numeric_summary,
            ),
            NormalizedSection(
                section_id="preview",
                order=2,
                heading="Preview",
                text=preview_rows,
            ),
        ]

        raw_text = "\n\n".join(section.text for section in sections)
        return NormalizedDocument(
            source=source,
            sections=sections,
            raw_text=raw_text,
            metadata={
                "rows": len(dataframe),
                "columns_count": len(dataframe.columns),
                "columns": [str(column) for column in dataframe.columns],
            },
        )
